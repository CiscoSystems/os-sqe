from lab.decorators import section


class CloudRouter(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self._dic = dic

    @property
    def id(self):
        return self._dic.get('id', self._dic['ID'])

    @property
    def name(self):
        return self._dic.get('name', self._dic['Name'])

    @staticmethod
    @section('Creating router (estimate 10 secs)')
    def create(cloud, name, on_nets, fip_net):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        name = UNIQUE_PATTERN_IN_NAME + name
        cloud.os_cmd(cmd='neutron router-create ' + name)
        for net in sorted(on_nets):
            cloud.os_cmd('neutron router-interface-add {} {}'.format(name, net.subname))
        cloud.os_cmd('neutron router-gateway-set {} {}'.format(name, fip_net.name))

    @staticmethod
    @section(message='cleanup routers (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = CloudRouter.list(cloud=cloud)
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        CloudRouter.delete(routers=lst)

    @staticmethod
    def delete(routers):
        import re
        import time

        if len(routers):
            ids = [s.id for s in routers]
            names = [s.name for s in routers]
            for r_id, name in zip(ids, names):
                routers[0].cloud.os_cmd('neutron router-gateway-clear ' + r_id, comment=name)
                ans = routers[0].cloud.os_cmd('neutron router-port-list {} '.format(r_id), comment=name)
                subnet_ids = [x['fixed_ips'].split(',')[0].split(':')[-1] for x in ans]
                map(lambda subnet_id: routers[0].cloud.os_cmd('neutron router-interface-delete {} {}'.format(r_id, subnet_id), comment=name), subnet_ids)
            for i in range(10):
                ans = routers[0].cloud.os_cmd(cmd='openstack router delete ' + ' '.join(ids), comment=' '.join(names), is_warn_only=True)
                if ans:
                    ids = re.findall("Failed .*ID '(?P<id>.*)':.*", ans)
                    names = ['attempt ' + str(i)]
                    time.sleep(2)
                else:
                    return
            else:
                raise RuntimeError('Failed to cleanup routers after 10 attempts')
            # cloud.os_cmd('neutron router-delete ' + r['id'], comment=r['name'])

    @staticmethod
    def list(cloud):
        return [CloudRouter(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack router list ')]
