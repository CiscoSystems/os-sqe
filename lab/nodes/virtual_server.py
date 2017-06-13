from lab.nodes.lab_server import LabServer


class VirtualServer(LabServer):
    def __init__(self, **kwargs):
        kwargs['model'] = 'virtual'
        kwargs['ru'] = 'virtual'
        super(VirtualServer, self).__init__(**kwargs)
        self._hard_server = self.pod.get_node_by_id(kwargs['virtual-on'])
        self._hard_server.add_virtual_server(self)

    def cmd(self, cmd):
        raise NotImplementedError()

    def get_hardware_server(self):
        return self._hard_server

    def vnc_display(self):
        import os

        name = self.get_node_id().replace('xrvr', 'xrnc')
        ans = self._hard_server.exe('virsh vncdisplay {}'.format(name))
        port = 5900 + int(ans.strip(':'))
        vts_host_ip = self._hard_server.get_ip_mx()
        mgmt_ip = self.pod.get_director().get_ip_api()
        os.system('ssh -2NfL {port}:{vts}:{port} root@{mgmt}'.format(port=port, vts=vts_host_ip, mgmt=mgmt_ip))

    def get_hard_node_id(self):
        return self._hard_server.get_node_id()