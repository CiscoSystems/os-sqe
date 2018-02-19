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

    def disrupt_libvirt(self, downtime):
        import time

        ans =self.hard.exe(cmd='virsh list --all; virsh suspend {}; virsh list --all'.format(self.id))
        if 'Domain {} suspended'.format(self.id) not in ans:
            raise RuntimeError('{}: failed to suspend libivrt domain: {}'.format(self, ans))
        time.sleep(downtime)
        ans = self.hard.exe(cmd='virsh resume {}; virsh list --all'.format(self.id))
        if 'Domain {} resumed'.format(self.id) not in ans:
            raise RuntimeError('{}: failed to suspend libvirt domain: {}'.format(self, ans))

    def disrupt_nic(self, method_to_disrupt, downtime):
        import time
        api_or_mgmt = 'api' if 'api' in method_to_disrupt else 'mgmt'

        ans = self.hard.exe('ip a | grep {}-{}'.format(self.id, api_or_mgmt))
        if_name = ans.split()[1][:-1]
        ans = self.hard.exe('ip l s dev {0} down; ip a s dev {0}'.format(if_name))
        if 'state DOWN' not in ans:
            raise RuntimeError('{}: failed to down iface: {}'.format(self, ans))
        self.log('iface={} status=down for downtime={}'.format(if_name, downtime))

        interval = downtime / 10
        for i in range(10):
            self.pod.nodes_dic['vtc'].r_vtc_crm_mon('inside')
            time.sleep(interval)

        ans = self.hard.exe('ip l s dev {0} up; ip a s dev {0}'.format(if_name))
        if 'UP' not in ans:
            raise RuntimeError('{}: failed to down iface: {}'.format(self, ans))
        self.log('iface={} status=up after downtime={}'.format(if_name, downtime))


class VipServer(LabServer):
    def __init__(self, pod, dic):
        dic['oob-ip'], dic['oob-username'], dic['oob-password'] = None, None, None
        super(VipServer, self).__init__(pod=pod, dic=dic)
        self.individuals = {}
        self.major = None

    def cmd(self, cmd):
        raise NotImplementedError()
