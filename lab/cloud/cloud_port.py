from lab.cloud import CloudObject


class CloudPort(CloudObject):
    STATUS_DOWN = 'DOWN'

    def __init__(self, cloud, net, dic):
        super(CloudPort, self).__init__(cloud=cloud, dic=dic)
        self.net_id = dic['network_id']
        self.subnet_id = dic['fixed_ips'].split('\"')[3]
        self.mac = dic['mac_address']
        self.ip = dic['fixed_ips'].split('\"')[-2]
        self.net = net
        net.ports.append(self)

    @staticmethod
    def create(cloud, server_number, on_nets, sriov=False):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        sriov_addon = '--binding:vnic-type direct' if sriov else ''
        ports = []
        for net in on_nets:
            ip, mac = net.calc_ip_and_mac(server_number)
            fixed_ip_addon = '--fixed-ip ip_address={ip} --mac-address {mac}'.format(ip=ip, mac=mac) if ip else ''
            port_name = UNIQUE_PATTERN_IN_NAME + str(server_number) + '-p' + ('-srvio' if sriov else '') + '-on-' + net.net_name
            dic = cloud.os_cmd(['neutron port-create  --name {port_name} {net_name} {ip_addon} {sriov_addon}'.format(port_name=port_name, net_name=net.net_name, ip_addon=fixed_ip_addon, sriov_addon=sriov_addon)])
            port = CloudPort(cloud=cloud, net=net, dic=dic)
            assert port.net_id == net.net_id, 'Port {} is created with wrong network_id'
            ports.append(port)
        return ports

    @staticmethod
    def delete(ports):
        if len(ports):
            ids = [p.port_id for p in ports]
            names = [p.port_name for p in ports]
            ports[0].cloud.os_cmd(cmd='openstack port delete ' + ' '.join(ids), comment=' '.join(names), is_warn_only=True)

    @staticmethod
    def list(cloud):
        class Tmp:
            def __init__(self, cloud, dic):
                self.cloud = cloud
                self.port_id = dic['ID']
                self.port_name = dic['Name']
        return [Tmp(cloud=cloud, dic=x) for x in cloud.os_cmd(['openstack port list '])]
