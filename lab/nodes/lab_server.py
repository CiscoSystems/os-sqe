from lab.nodes import LabNode
from lab.server import Server


class LabServer(LabNode, Server):

    def __init__(self, node_id, role, lab):
        self._tmp_dir_exists = False
        self._package_manager = None
        self._mac_server_part = None

        LabNode.__init__(self, node_id=node_id, role=role, lab=lab)
        Server.__init__(self, ip='Not defined in lab_server.py', username='Not defined in lab_server.py', password='Not defined in lab_server.py')

    def __repr__(self):
        ssh_ip, ssh_u, ssh_p = self.get_ssh()
        oob_ip, oob_u, oob_p = self.get_oob()

        return u'{l} {n} | sshpass -p {p1} ssh {u1}@{ip1} ipmitool -I lanplus -H {ip2} -U {u2} -P {p2}'.format(l=self.lab(), n=self.get_id(), ip1=ssh_ip, p1=ssh_p, u1=ssh_u, ip2=oob_ip, p2=oob_p, u2=oob_u)

    def cmd(self, cmd):
        raise NotImplementedError

    def add_nic(self, nic_name, ip_or_index, net, on_wires):
        import validators
        from lab.network import Nic

        ip_or_index = ip_or_index or self._assign_default_ip_index(net)

        try:
            index = int(ip_or_index)  # this is shift in the network
            if index in [0, 1, 2, 3, -1]:
                raise IndexError('{}:  index={} is not possible since 0 =>  network address [1,2,3] => GW addresses -1 => broadcast address'.format(self.get_id(), index))
            try:
                net.get_ip_for_index(index)
            except (IndexError, ValueError):
                raise IndexError('{}: index {} is out of bound of {}'.format(self.get_id(), index, net))
        except ValueError:
            if validators.ipv4(str(ip_or_index)):
                try:
                    index, ip = {x: str(net.get_ip_for_index(x)) for x in range(net.get_size()) if str(ip_or_index) in str(net.get_ip_for_index(x))}.items()[0]
                except IndexError:
                    raise ValueError('{}: ip {} is out of bound of {}'.format(self.get_id(), ip_or_index, net))
            else:
                raise ValueError('{}: specified value "{}" is neither ip nor index in network'.format(self.get_id(), ip_or_index))

        nic = Nic(name=nic_name, node=self, net=net, net_index=index, on_wires=on_wires)
        self._nics[nic_name] = nic
        if nic.is_ssh():
            self.set_ssh_ip(ip=nic.get_ip_and_mask()[0])
        return nic

    def r_is_nics_correct(self):
        actual_nics = self.r_list_ip_info(connection_attempts=1)
        if not actual_nics:
            return False

        status = True
        for nic in self.get_nics().values():
            requested_macs = nic.get_macs()
            requested_ip = nic.get_ip_with_prefix()
            requested_names = nic.get_names()
            for name in requested_names:
                if name not in actual_nics:
                    self.log(message='has no NIC {}'.format(name), level='warning')
                    status = False
                if not nic.is_pxe() and requested_ip not in actual_nics[name]['ipv4']:  # this ip might be re-assign to the bridge which has this NIC inside
                    br_name = 'br-' + name[:-1]
                    if br_name not in actual_nics or requested_ip not in actual_nics[br_name]['ipv4']:
                        self.log(message='NIC "{}" has different IP  actual: {}  requested: {}'.format(nic.get_name(), actual_nics[name]['ipv4'] + actual_nics[br_name]['ipv4'], requested_ip), level='warning')
                        status = False
                actual_mac = actual_nics[name]['mac'].upper()
                if actual_mac != requested_macs.upper():
                    self.log(message='NIC {} has different mac: actual {} requested {}'.format(name, actual_mac, requested_macs), level='warning')
                    status = False
        return status
