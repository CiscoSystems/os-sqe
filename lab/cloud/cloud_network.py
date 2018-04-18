from lab.cloud import CloudObject


class CloudNetwork(CloudObject):
    STATUS_ACTIVE = 'ACTIVE'

    def __init__(self, cloud, dic):
        super(CloudNetwork, self).__init__(cloud=cloud, dic=dic)
        self.segmentation_id = str(dic.get('provider:segmentation_id') or dic.get('provider-segmentation-id'))
        self.network_type = dic.get('provider:network_type') or dic.get('provider-network-type', '').strip('cisco-vts-identities:')
        self.physnet = dic.get('provider:physical_network') or dic.get('provider-physical-network')
        self.net_status = dic['status'].strip('cisco-vts-openstack-identities:')
        self.mtu = None
        self.subnets = []
        self.ports = []

    @property
    def is_external(self):
        return self.dic_from_os['router:external'] == 'External'

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id

    def calc_ip_and_mac(self, index):
        from netaddr import IPNetwork

        n = IPNetwork(self.subnets[0].cidr)
        ip = str(n[(index / 100) * 256 + index % 100])                                                                  # special variant index 99 gives 99.0.0.99 199 gives 99.0.1.99
        mac = 'cc:' + ':'.join(map(lambda x: '{0:02}'.format(int(x)), ip.split('.'))) + ':{:02}'.format(n.prefixlen)    # mac coincides with ip: 99.0.3.25/16 -> cc:99:00:03:25:16
        return ip, mac

    @staticmethod
    def create(how_many, common_part_of_name, cloud, class_a=99, vlan_id=0, is_dhcp=False):
        from netaddr import IPNetwork
        from lab.cloud.cloud_subnet import CloudSubnet

        dns = ' --dns-nameserver 171.70.168.183' if class_a == 99 else ''
        dhcp = ' --dhcp' if is_dhcp else ' --no-dhcp'
        net_cmd = 'openstack network create {net_name} {phys} -f json'
        a_pool = '--allocation-pool start={p1},end={p2}' if class_a == 99 else ''

        sub_cmd = 'openstack subnet create --network {net_name} --subnet-range {cidr} --gateway {gw}' + a_pool + dhcp + dns + ' {subnet_name} -f json'

        def phys(a):
            return '--provider:physical_network=physnet1 --provider:network_type=vlan --provider:segmentation_id=' + str(vlan_id + a) if vlan_id else ''

        nets = []
        for i in range(1, how_many+1):
            net_name = '{}{}net{}'.format(CloudObject.UNIQUE_PATTERN_IN_NAME, common_part_of_name, i)
            subnet_name = net_name.replace('net', 'subnet')
            network = IPNetwork('{}.{}.0.0/16'.format(class_a, i))

            cidr, gw, start, stop = network, network[-10], network[10], network[100]
            ans = cloud.os_cmd([net_cmd.format(net_name=net_name, phys=phys(i)), sub_cmd.format(net_name=net_name, cidr=cidr, subnet_name=subnet_name, gw=gw, p1=start, p2=stop)])
            nets.append(CloudNetwork(cloud=cloud, dic=ans[0]))
            CloudSubnet(cloud=cloud, dic=ans[1])
        return nets
