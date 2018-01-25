from lab.cloud import CloudObject


class CloudPort(CloudObject):
    STATUS_DOWN = 'DOWN'

    def __init__(self, cloud, dic):
        super(CloudPort, self).__init__(cloud=cloud, dic=dic)
        self.mac = dic['mac_address']
        self.ip = dic['fixed_ips'].split(',')[0].strip('ip_address=\'\\')
        self.net = filter(lambda x: x.id == dic['network_id'], self.cloud.nets)[0]

    @staticmethod
    def create(cloud, server_number, on_nets, sriov=False):
        sriov_addon = '--binding:vnic-type direct' if sriov else ''
        ports = []
        for net in on_nets:
            ip, mac = net.calc_ip_and_mac(server_number)
            fixed_ip_addon = '--fixed-ip ip-address={ip} --mac-address {mac}'.format(ip=ip, mac=mac) if ip else ''
            port_name = CloudObject.UNIQUE_PATTERN_IN_NAME + '-p' + str(server_number) + ('-srvio' if sriov else '') + '-on-' + net.name
            l = cloud.os_cmd(['openstack port create {} --network {} {} {} -f json'.format(port_name, net.name, fixed_ip_addon, sriov_addon)])
            port = CloudPort(cloud=cloud, dic=l[0])
            ports.append(port)
        return ports
