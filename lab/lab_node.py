import abc


class LabNode(object):
    __metaclass__ = abc.ABCMeta

    def __repr__(self):
        ssh_ip, ssh_u, ssh_p = self.get_ssh()
        oob_ip, oob_u, oob_p = self.get_oob()
        return u'{l} {n} | sshpass -p {p1} ssh {u1}@{ip1} ipmitool -I lanplus -H {ip2} -U {u2} -P {p2}'.format(l=self.lab(), n=self.get_id(), ip1=ssh_ip, p1=ssh_p, u1=ssh_u, ip2=oob_ip, p2=oob_p, u2=oob_u)

    def __init__(self, node_id, role, lab, hostname):
        self._lab = lab  # link to parent Laboratory object
        self._id = node_id  # some id which unique in the given role, usually role + some small integer
        self._role = role  # which role this node play, possible roles are defined in Laboratory
        self._n = lab.count_node(role)  # number of this node in a list of nodes for this role
        self._hostname = hostname  # usually it's actual hostname as reported by operation system of the node
        self._ssh_username, self._ssh_password = 'Default in LabNode.__init__()', 'Default in LabNode.__init__()'
        self._oob_ip, self._oob_username, self._oob_password = 'Default in LabNode.__init__()', 'Default in LabNode.__init__()', 'Default in LabNode.__init__()'
        self._nics = dict()  # list of NICs
        self._is_deploy_by_cobbler = False
        self._ru, self._model = 'Default in LabNod.__init()', 'Default in LabNod.__init()'

        self._upstream_wires = []
        self._downstream_wires = []
        self._peer_link_wires = []

    def wire_upstream(self, wire):
        self._upstream_wires.append(wire)

    def wire_downstream(self, wire):
        self._downstream_wires.append(wire)

    def wire_peer_link(self, wire):
        self._peer_link_wires.append(wire)

    def set_deploy_by_cobbler(self):
        self._is_deploy_by_cobbler = True

    def is_deploy_by_cobbler(self):
        return self._is_deploy_by_cobbler

    def get_id(self):
        return self._id

    def get_role(self):
        return self._role

    def lab(self):
        return self._lab

    def get_ssh(self):
        return self.get_ssh_ip(), self._ssh_username, self._ssh_password

    def get_ssh_ip(self):
        ssh_nic = filter(lambda nic: nic.is_ssh(), self.get_nics().values())
        return ssh_nic[0].get_ip_and_mask()[0] if ssh_nic else 'Not yet assigned'

    def get_oob(self):
        return self._oob_ip, self._oob_username, self._oob_password

    def set_oob_creds(self, ip, username, password):
        self._oob_ip, self._oob_username, self._oob_password = ip, username, password

    def set_ssh_creds(self, username, password):
        self._ssh_username, self._ssh_password = username, password

    def hostname(self):
        return self._hostname

    def get_all_wires(self):
        """Returns all ires"""
        return self._downstream_wires + self._upstream_wires

    def add_nic(self, nic_name, mac_or_pattern, ip_or_index, net, on_wires):
        import validators
        from lab.network import Nic

        if ip_or_index:
            try:
                index = int(ip_or_index)  # this is shift in the network
                if index in [0, 1, 2, 3, -1]:
                    raise ValueError('{}:  index={} is not possible since 0 =>  network address [1,2,3] => GW addresses -1 => broadcast address'.format(self.get_id(), index))
                try:
                    ip = net[index]
                except (IndexError, ValueError):
                    raise ValueError('{}: index {} is out of bound of {}'.format(self.get_id(), index, net))
            except ValueError:
                if validators.ipv4(str(ip_or_index)):
                    try:
                        index, ip = {x: str(net[x]) for x in range(net.size) if str(ip_or_index) in str(net[x])}.items()[0]
                    except IndexError:
                        raise ValueError('{}: ip {} is out of bound of {}'.format(self.get_id(), ip_or_index, net))
                else:
                    raise ValueError('{}: specified value "{}" is neither ip nor index in network'.format(self.get_id(), ip_or_index))
            self.lab().make_sure_that_object_is_unique(obj=ip, node_id=self.get_id())
        else:
            index = 'Not defined in lab yaml as detected by LabNode.add_nic()'

        mac = mac_or_pattern if validators.mac_address(str(mac_or_pattern)) else self.form_mac(mac_or_pattern)

        self.lab().make_sure_that_object_is_unique(obj=mac, node_id=self.get_id())

        nic = Nic(name=nic_name, mac=mac, node=self, net=net, net_index=index, on_wires=on_wires)
        self._nics[nic_name] = nic
        return nic

    def get_nic(self, nic):
        try:
            return self._nics[nic]
        except KeyError:
            return RuntimeError('{}: is not on {} network'.format(self.get_id(), nic))

    def get_nics(self):
        return self._nics

    def get_vlans(self):
        """ Get all vlans which need to reach this server"""
        vlans = []
        for nic in self.get_nics():
            vlans.extend(nic.get_vlans())
        return vlans

    @abc.abstractmethod
    def cmd(self, cmd):
        pass  # this method allows to do OOB commands like e.g. CIMC or NXAPI

    def form_mac(self, pattern):
        raise NotImplementedError('{}.form_mac() is not implemented'.format(type(self)))  # this method forms mac based on lab id node id and provided pattern

    def set_hardware_info(self, ru, model):
        self._ru, self._model = ru, model

    def get_hardware_info(self):
        return self._ru, self._model
