from lab.decorators import section


class CloudPort(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self._dic = dic

    @property
    def id(self):
        return self._dic.get('ID') or self._dic['id']

    @property
    def name(self):
        return self._dic['Name']

    @staticmethod
    @section(message='cleanup ports (estimate 5 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = filter(lambda p: p.name not in ['admin', 'service'], CloudPort.list(cloud=cloud))
        if not is_all:
            lst = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], lst)
        CloudPort.delete(ports=lst)

    @staticmethod
    def create(cloud, server_number, net_name, ip, mac, sriov=False):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        sriov_addon = '--binding:vnic-type direct' if sriov else ''
        fixed_ip_addon = '--fixed-ip ip_address={ip} --mac-address {mac}'.format(ip=ip, mac=mac) if ip else ''
        port_name = UNIQUE_PATTERN_IN_NAME + server_number + '-p' + ('-srvio' if sriov else '') + '-on-' + net_name
        dic = cloud.os_cmd('neutron port-create -f json --name {port_name} {net_name} {ip_addon} {sriov_addon}'.format(port_name=port_name, net_name=net_name, ip_addon=fixed_ip_addon, sriov_addon=sriov_addon))
        return CloudPort(cloud=cloud, dic=dic)

    @staticmethod
    def delete(ports):
        import re
        import time

        if len(ports):
            ids = [p.id for p in ports]
            names = [p.name for p in ports]
            for i in range(10):
                ans = ports[0].cloud.os_cmd(cmd='openstack port delete ' + ' '.join(ids), comment=' '.join(names), is_warn_only=True)
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
        return [CloudPort(cloud=cloud, dic=x) for x in cloud.os_cmd('openstack port list -f json')]
