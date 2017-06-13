from lab.decorators import section


class CloudRouter(object):
    def __init__(self, cloud, router_dic):
        self.cloud = cloud
        self._dic = router_dic

    @property
    def id(self):
        return self._dic['id']

    @property
    def name(self):
        return self._dic['name']

    @staticmethod
    @section('Creating router')
    def create(cloud, name, on_nets, fip_net):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        name = UNIQUE_PATTERN_IN_NAME + name
        cloud.os_cmd(cmd='neutron router-create ' + name)
        for net in sorted(on_nets):
            cloud.os_cmd('neutron router-interface-add {} {}'.format(name, net.subname))
        cloud.os_cmd('neutron router-gateway-set {} {}'.format(name, fip_net.name))

    @staticmethod
    @section(message='cleanup routers', estimated_time=3)
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = cloud.os_cmd('neutron router-list -f json')
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        for r in lst:
            cloud.os_cmd('neutron router-gateway-clear ' + r['id'], comment=r['name'])
            ans = cloud.os_cmd('neutron router-port-list {} -f json'.format(r['id']), comment=r['name'])
            subnet_ids = [x['fixed_ips'].split(',')[0].split(':')[-1] for x in ans]
            map(lambda subnet_id: cloud.os_cmd('neutron router-interface-delete {} {}'.format(r['id'], subnet_id), comment=r['name']), subnet_ids)
            cloud.os_cmd('neutron router-delete ' + r['id'], comment=r['name'])
