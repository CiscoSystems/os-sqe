import abc

from lab.with_log import WithLogMixIn
from lab.with_config import WithConfig


class LabNode(WithLogMixIn, WithConfig):
    __metaclass__ = abc.ABCMeta

    _ROLE_VS_COUNT = {}

    def __init__(self, node_id, role, lab, cfg=None):
        self._lab = lab     # link to parent Laboratory object
        self._id = node_id  # some id which unique in the given role, usually role + some small integer
        self._role = role   # which role this node play, possible roles are defined in Laboratory
        role = role.split('-')[0]  # e.g. control-fi and control-cimc are the same for counting
        self._ROLE_VS_COUNT.setdefault(role, 0)
        self._ROLE_VS_COUNT[role] += 1
        self._n = self._ROLE_VS_COUNT[role]  # number of this node in a list of nodes for this role
        self._oob_ip, self._oob_username, self._oob_password = 'ip_XXX', 'us_XXX', 'pass_XXX'
        self._nics = dict()  # list of NICs
        self._ru, self._model = 'RU_XXX', 'MODEL_XXX'
        self._cfg = cfg  # initial configuration dictionary as provided in lab config file

        self._wires = []

    def __repr__(self):
        return u'{} {}'.format(self.get_lab_id(), self.get_node_id())

    @staticmethod
    def add_node(lab, node_desc):
        try:
            node_id = node_desc['id']
            role = node_desc['role']

            klass = lab.get_role_class(role)
            node = klass(lab=lab, node_id=node_id, role=role, cfg=node_desc)

            try:
                node.set_oob_creds(ip=node_desc['oob-ip'], username=node_desc['oob-username'], password=node_desc['oob-password'])
                node.set_hardware_info(ru=node_desc.get('ru', 'RU-XXX'), model=node_desc.get('model', 'MODEL-XXX'))
                if hasattr(node, 'set_ssh_creds'):
                    node.set_ssh_creds(username=node_desc['ssh-username'], password=node_desc['ssh-password'])
                if hasattr(node, 'set_hostname'):
                    node.set_hostname(node_desc.get('hostname', '{}.ctocllab.cisco.com'.format(node_id)))
                if hasattr(node, 'set_ucsm_id'):
                    node.set_ucsm_id(node_desc['ucsm-id'])
                if hasattr(node, 'set_vip'):
                    node.set_vip(node_desc['vip'])
                if hasattr(node, 'set_sriov'):
                    node.set_sriov(node_desc['sriov'])
                return node
            except KeyError as ex:
                raise ValueError('Node "{}": has no "{}"'.format(node_id, ex.message))
        except KeyError as ex:
            ValueError('"{}" for node "{}" is not provided'.format(ex.message, node_desc))
        except TypeError as ex:
            raise TypeError('{} for the node {} of role {}'.format(ex, node_desc.get('id'), node_desc.get('role')))

    def connect_node(self):
        """This is not server so process just wires information for upstream links. LabServer has this method overridden"""
        from lab.wire import Wire

        for local_port_id, peer_desc in self._cfg.get('wires', {}).items():  # node might have no wires
            Wire.add_wire(local_node=self, local_port_id=local_port_id, peer_desc=peer_desc)

    def get_ssh_for_bash(self):
        return 'sshpass -p {} ssh {}@{}'.format(self._oob_password, self._oob_username, self._oob_ip)

    def attach_wire(self, wire):
        self._wires.append(wire)

    def get_node_id(self):
        return self._id

    def get_lab_id(self):
        return str(self.lab())

    def get_role(self):
        return self._role

    def get_peer_link_wires(self):
        return [x for x in self._wires if x.is_n9_n9()]

    def get_n_in_role(self):
        return self._n

    def lab(self):
        return self._lab

    def get_oob(self):
        return self._oob_ip, self._oob_username, self._oob_password

    def set_oob_creds(self, ip, username, password):
        self._oob_ip, self._oob_username, self._oob_password = ip, username, password

    def get_all_wires(self):
        """Returns all wires"""
        return self._wires

    def get_wires_to(self, node):
        """Returns wires to given node"""
        return filter(lambda x: x.get_peer_node(self) == node, self.get_all_wires())

    def get_nic(self, nic):
        try:
            return self._nics[nic]
        except KeyError:
            return RuntimeError('{}: is not on {} network'.format(self.get_node_id(), nic))

    def get_nics(self):
        return self._nics

    def get_ip_api(self):
        return self.get_nic('a').get_ip_and_mask()[0]

    def get_ip_api_with_prefix(self):
        return self.get_nic('a').get_ip_with_prefix()

    def get_ip_mx(self):
        return self.get_nic('mx').get_ip_and_mask()[0]

    def get_ip_mx_with_prefix(self):
        return self.get_nic('mx').get_ip_with_prefix()

    def get_gw_mx_with_prefix(self):
        return self.get_nic('mx').get_gw_with_prefix()

    def get_ip_t(self):
        return self.get_nic('t').get_ip_and_mask()[0]

    def get_ip_t_with_prefix(self):
        return self.get_nic('t').get_ip_with_prefix()

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI

    def set_hardware_info(self, ru, model):
        self._ru, self._model = ru, model

    def get_hardware_info(self):
        return self._ru, self._model

    def is_cimc_server(self):
        from lab.cimc import CimcServer

        return isinstance(self, CimcServer)

    def is_fi_server(self):
        from lab.nodes.fi import FiServer

        return isinstance(self, FiServer)

    def is_director(self):
        from lab.nodes.fi import FiDirector
        from lab.cimc import CimcDirector

        return type(self) in [FiDirector, CimcDirector]

    def is_controller(self):
        from lab.nodes.fi import FiController
        from lab.cimc import CimcController

        return type(self) in [FiController, CimcController]

    def is_compute(self):
        from lab.nodes.fi import FiCompute
        from lab.cimc import CimcCompute

        return type(self) in [FiCompute, CimcCompute]

    def is_ceph(self):
        from lab.nodes.fi import FiCeph
        from lab.cimc import CimcCeph

        return type(self) in [FiCeph, CimcCeph]

    def is_vts_host(self):
        from lab.vts_classes.vtc import VtsHost

        return type(self) == VtsHost

    def is_vtc(self):
        from lab.vts_classes.vtc import Vtc

        return type(self) == Vtc

    def is_xrvr(self):
        from lab.vts_classes.xrvr import Xrvr

        return type(self) == Xrvr

    def is_vtf(self):
        from lab.vts_classes.vtf import Vtf

        return type(self) == Vtf

    def is_virtual(self):
        return any([self.is_vtc(), self.is_xrvr(), self.is_vtf()])

    def get_yaml_body(self):

        a = ' {{id: "{}", role: {}, oob-ip: {}, ssh-username: None, ssh-password: None, oob-username: "{}", oob-password: "{}", '.format(self._id, self._role, self._oob_ip, self._oob_username, self._oob_password)
        a += 'hostname: "{}", model: "{}", ru: "{}"'.format('1', self._model, self._ru)

        if self._wires:
            wires = ',\n              '.join(map(lambda x: x.get_yaml_body(), self._wires))
            a += ',\n      wires: {{{}\n      }}'.format(wires)
        else:
            a += '\n'
        if self.get_nics():
            nics = ',\n              '.join(map(lambda x: x.get_yaml_body(), self.get_nics().values()))
            a += ',\n      nics:  {{{}\n      }}\n'.format(nics)
        else:
            a += '\n'
        a += ' }'
        return a

    def calculate_mac(self, port_id, mac):
        import validators

        mac = str(mac)
        if not validators.mac_address(mac):
            if self.is_cimc_server():
                o2 = 'A0'  # UCS connected to N9
            elif self.is_fi_server():
                server_id = getattr(self, 'get_server_id')()  # UCS connected to FI
                o2 = 'B' + server_id.split('/')[-1] if '/' in server_id else 'C' + server_id
            else:
                o2 = 'E9'  # virtual machines

            if self.is_director():
                o3 = 'DD'
            elif self.is_controller():
                o3 = 'CC'
            elif self.is_compute():
                o3 = 'C0'
            elif self.is_ceph():
                o3 = 'CE'
            elif self.is_vtc():
                o3 = 'F0'
            elif self.is_xrvr():
                o3 = 'F1'
            elif self.is_vtf():
                o3 = 'F2'
            elif self.is_vts_host():
                o3 = 'F5'
            else:
                return None
            mac = '{}0:{:02}:{}:{}:{:02}:CA'.format('1' if port_id == 'MLOM/1' else '0', self.lab().get_id(), o2, o3, self._n)
        return mac

    def r_verify_oob(self):
        import socket

        ip, _, _ = self.get_oob()
        if ip == 'MatchSSH':  # it's a virtual node no OOB
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ok = None
        s.settimeout(2)
        try:
            s.connect((ip, 22))
            ok = 'ok'
        except (socket.timeout, socket.error):
            ok = 'FAILED'
        finally:
            self.log('OOB ({}) is {}'.format(ip, ok))
            s.close()
