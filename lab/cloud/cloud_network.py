from lab.decorators import section


class CloudNetwork(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self._dic = dic

    @property
    def net_id(self):
        return self._dic.get('id') or self._dic['ID']

    @property
    def net_name(self):
        return self._dic.get('name') or self._dic['Name']

    @property
    def subnet_id(self):
        return self._dic['subid']

    @property
    def segmentation_id(self):
        return self._dic['provider:segmentation_id']

    def calc_ip_with_prefix(self, index):
        return '{}/{}'.format(self._dic['network'][index], self._dic['network'].prefixlen)

    def calc_ip(self, index):
        # special variant index 99 gives 1.0.0.99 199 gives 1.0.1.99
        return str(self._dic['network'][(index / 100) * 256 + index % 100])

    def calc_mac(self, index):
        ip = self.calc_ip(index=index)
        return 'cc:' + ':'.join(map(lambda n: '{0:02}'.format(int(n)), str(ip).split('.'))) + ':' + str(self._dic['network'].prefixlen)

    @staticmethod
    def create(how_many, common_part_of_name, cloud, class_a=10, vlan_id=0, is_dhcp=False):
        from netaddr import IPNetwork
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        dns = '171.70.168.183'

        d_h = '--dns-nameserver ' + dns
        d_h += '--dhcp' if is_dhcp else ' --no-dhcp'  # '' if is_dhcp else '--disable-dhcp'
        # net_cmd = 'neutron net-create {} {} -f json'
        net_cmd = 'openstack network create {net_name} {phys} -f json'
        # sub_cmd = 'neutron subnet-create            {net_name}                {cidr} --gateway {gw} --allocation-pool start={p1},end={p2} ' + d_h + ' --name {subnet_name} -f json'
        sub_cmd = 'openstack subnet create --network {net_name} --subnet-range {cidr} --gateway {gw} --allocation-pool start={p1},end={p2} ' + d_h + ' {subnet_name} -f json'

        def phys(i):
            return '--provider:physical_network=physnet1 --provider:network_type=vlan --provider:segmentation_id=' + str(vlan_id + i) if vlan_id else ''

        nets = []
        for i in range(1, how_many+1):
            net_name = '{}-{}-net-{}'.format(UNIQUE_PATTERN_IN_NAME, common_part_of_name, i)
            subnet_name = net_name.replace('-net-', '-subnet-')
            network = IPNetwork('{}.{}.0.0/16'.format(class_a, i))

            cidr, gw, start, stop = network, network[-10], network[10], network[100]
            d1 = cloud.os_cmd(net_cmd.format(net_name=net_name, phys=phys(i)))
            d2 = cloud.os_cmd(sub_cmd.format(net_name=net_name, cidr=cidr, subnet_name=subnet_name, gw=gw, p1=start, p2=stop))

            for key in set(d1.keys()) & set(d2.keys()):
                d2['sub' + key] = d2[key]
                del d2[key]
            d1.update(d2)
            d1['network'] = network
            nets.append(CloudNetwork(cloud=cloud, dic=d1))
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
        return [CloudNetwork(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack network list -f json')]
