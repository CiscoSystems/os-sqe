from lab.base_lab import LabWorker


class DeployerExisting(LabWorker):

    @staticmethod
    def sample_config():
        return '1.2.3.4'

    def __init__(self, ip):
        from lab.laboratory import Laboratory

        name_to_ip = {'g7-2': '10.23.221.142', 'marahaika': '10.23.228.228', 'c35bottom': '172.26.232.151', 'i11tb3': '10.30.117.6',
                      'i13-tb1': '10.30.116.206',  'c42-mid': '172.28.165.31', 'mdc2': '172.29.86.38', 'skullcrusher': '10.23.229.126', 'c43-bot': '172.26.233.230', 'c42top': '172.28.165.111',
                      'hiccup': '172.31.228.196',  'rcdn-nfvi-c': '10.201.36.50', 'j10-tb1': '10.30.117.238', 'sjc04-c38': '172.26.229.46', 'c33-tb2-mpod': '172.26.232.144', 'sjc-i13-tb4': '172.29.87.100',
                      'c43-nfvi': '172.26.233.230', 'c42-ucsd': '172.28.165.85', 'c44-bot': '172.26.233.80', 'merc-reg-tb1': '172.29.84.228', 'J11': '10.23.220.150'}

        self.pod = Laboratory.create_from_remote(ip=name_to_ip.get(ip, ip))

    @staticmethod
    def _its_ospd_installation(lab, list_of_servers):
        import re

        director = lab.get_director()

        net = lab.get_ssh_net()
        ssh_ip_pattern = '({0}.*)/{1}'.format(str(net).rsplit('.', 1)[0], net.prefixlen)
        re_ip = re.compile(ssh_ip_pattern)
        lines = director.exe('source stackrc && nova list').split('\n')
        for line in lines:
            if '=' in line:
                local_ip = line.split('=')[-1].split()[0]
                #  name = line.split('|')[2]
                ip_a_ans = director.exe('ssh -o StrictHostKeyChecking=no {local_ip} ip -o a'.format(local_ip=local_ip))
                ip = re_ip.findall(ip_a_ans)
                filter(lambda srv: srv.ip() == ip, list_of_servers)

    def deploy_cloud(self, clouds_and_servers):
        from lab.cloud.openstack import OS

        if not clouds_and_servers['servers']:
            clouds_and_servers['servers'].append(self.pod.mgmt)
            clouds_and_servers['servers'].extend(self.pod.controls)
            clouds_and_servers['servers'].extend(self.pod.computes)

        mgm = clouds_and_servers['servers'][0]
        openrc_path = None
        for path in ['/root/openstack-configs/openrc', '/home/stack/overcloudrc', '/root/keystonerc_admin']:
            ans = mgm.exe(command='sudo ls {}'.format(path), is_warn_only=True)
            if 'No such file or directory' not in ans:
                openrc_path = path
                break

        if openrc_path is None:
            raise RuntimeError('{}: "{}" does not contain any valid cloud'.format(self, self.pod))
        mgm.r_create_sqe_user()
        mgm.exe_as_sqe('rm -f openrc && sudo cp {} openrc && sudo chown sqe.sqe openrc'.format(openrc_path))
        return OS(name=self.pod, mediator=mgm, openrc_path='openrc')

    def execute(self, servers):
        cloud = self.deploy_cloud(servers)
        return cloud
