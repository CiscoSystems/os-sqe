from lab.decorators import section


class CloudNetwork(object):
    STATUS_ACTIVE = 'ACTIVE'

    def __init__(self, cloud, net_dic, subnet_dic=None):
        self.cloud = cloud
        self.net_id = net_dic.get('id') or net_dic['ID']
        self.net_name = net_dic.get('name') or net_dic['Name']
        self.segmentation_id = str(net_dic.get('provider:segmentation_id') or net_dic.get('provider-segmentation-id'))
        self.network_type = net_dic.get('provider:network_type') or net_dic.get('provider-network-type').strip('cisco-vts-identities:')
        self.physnet = net_dic.get('provider:physical_network') or net_dic.get('provider-physical-network')
        self.net_status = net_dic['status'].strip('cisco-vts-openstack-identities:')
        self.mtu = str(net_dic['mtu'])
        if subnet_dic:
            assert self.net_id == (subnet_dic.get('network_id') or subnet_dic.get('network-id')), 'network id in subnet dic not coincide with id in network dic'
            self.cidr = subnet_dic['cidr']
            self.subnet_id = subnet_dic['id']
            self.subnet_name = subnet_dic['name']
            self.gateway_ip = subnet_dic.get('gateway_ip') or subnet_dic.get('gateway-ip')
            self.allocation_pool = subnet_dic.get('allocation_pools') or (subnet_dic.get('allocation-pools')[0]['start'] + '-' + subnet_dic.get('allocation-pools')[0]['end'])
        self.ports = []

    def __hash__(self):
        return hash(self.net_id)

    def __eq__(self, other):
        return self.net_id == other.net_id

    def calc_ip_and_mac(self, index):
        from netaddr import IPNetwork

        n = IPNetwork(self.cidr)
        ip = str(n[(index / 100) * 256 + index % 100])                                     # special variant index 99 gives 99.0.0.99 199 gives 99.0.1.99
        mac = 'cc:ab:' + ':'.join(map(lambda n: '{0:02}'.format(int(n)), ip.split('.')))      # mac coincides with ip: 99.0.3.25 -> cc:ab:99:00:03:25
        return ip, mac

    @staticmethod
    def create(how_many, common_part_of_name, cloud, class_a=99, vlan_id=0, is_dhcp=False):
        from netaddr import IPNetwork
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        dns = '171.70.168.183'

        d_h = '--dns-nameserver ' + dns
        d_h += '--dhcp' if is_dhcp else ' --no-dhcp'  # '' if is_dhcp else '--disable-dhcp'
        # net_cmd = 'neutron net-create {} {} -f json'
        net_cmd = 'openstack network create {net_name} {phys} -f json'
        # sub_cmd = 'neutron subnet-create            {net_name}                {cidr} --gateway {gw} --allocation-pool start={p1},end={p2} ' + d_h + ' --name {subnet_name} -f json'
        sub_cmd = 'openstack subnet create --network {net_name} --subnet-range {cidr} --gateway {gw} --allocation-pool start={p1},end={p2} ' + d_h + ' {subnet_name} -f json'

        def phys(a):
            return '--provider:physical_network=physnet1 --provider:network_type=vlan --provider:segmentation_id=' + str(vlan_id + a) if vlan_id else ''

        nets = []
        for i in range(1, how_many+1):
            net_name = '{}{}-net-{}'.format(UNIQUE_PATTERN_IN_NAME, common_part_of_name, i)
            subnet_name = net_name.replace('-net-', '-subnet-')
            network = IPNetwork('{}.{}.0.0/16'.format(class_a, i))

            cidr, gw, start, stop = network, network[-10], network[10], network[100]
            d1 = cloud.os_cmd(net_cmd.format(net_name=net_name, phys=phys(i)))
            d2 = cloud.os_cmd(sub_cmd.format(net_name=net_name, cidr=cidr, subnet_name=subnet_name, gw=gw, p1=start, p2=stop))
            nets.append(CloudNetwork(cloud=cloud, net_dic=d1, subnet_dic=d2))
        return nets

    @staticmethod
    @section(message='cleanup networks (estimate 10 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = CloudNetwork.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        CloudNetwork.delete(networks=lst)

    @staticmethod
    def delete(networks):
        import re
        import time

        if len(networks):
            ids = [s.net_id for s in networks]
            names = [s.net_name for s in networks]
            for i in range(10):
                ans = networks[0].cloud.os_cmd(cmd='openstack network delete ' + ' '.join(ids), comment=' '.join(names), is_warn_only=True)
                if ans:
                    ids = re.findall("Failed .*ID '(?P<id>.*)':.*", ans)
                    names = ['attempt ' + str(i)]
                    time.sleep(2)
                else:
                    return
            else:
                raise RuntimeError('Failed to cleanup networks after 10 attempts')

    @staticmethod
    def list(cloud):
        class Tmp:
            def __init__(self, cloud,  dic):
                self.cloud = cloud
                self.net_id = dic['ID']
                self.net_name = dic['Name']
        return [Tmp(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack network list -f json')]
