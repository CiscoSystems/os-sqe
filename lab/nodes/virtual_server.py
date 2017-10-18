from lab.nodes.lab_server import LabServer


class VirtualServer(LabServer):
    def __init__(self, pod, dic):
        dic.update({'oob-ip': None, 'oob-username': None, 'oob-password': None})
        super(VirtualServer, self).__init__(pod=pod, dic=dic)
        self.hard = self.pod.nodes_dic[dic['virtual-on']]
        self.hard.add_virtual_server(self)

    def cmd(self, cmd):
        raise NotImplementedError()


class LibVirtServer(VirtualServer):
    def r_libvirt_info(self):
        self.hard.exe('virsh list')

    def cmd(self, cmd):
        raise NotImplementedError()

    def vnc_display(self):
        import os

        name = self.id.replace('xrvr', 'xrnc')
        ans = self.hard.exe('virsh vncdisplay {}'.format(name))
        port = 5900 + int(ans.strip(':'))
        vts_host_ip = self.hard.get_ip_mx()
        mgmt_ip = self.pod.get_director().get_ip_api()
        os.system('ssh -2NfL {port}:{vts}:{port} root@{mgmt}'.format(port=port, vts=vts_host_ip, mgmt=mgmt_ip))


class VipServer(LabServer):
    def __init__(self, pod, dic):
        dic['oob-ip'], dic['oob-username'], dic['oob-password'] = None, None, None
        super(VipServer, self).__init__(pod=pod, dic=dic)
        self.individuals = {}

    def cmd(self, cmd):
        raise NotImplementedError()
