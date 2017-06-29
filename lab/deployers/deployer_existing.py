from lab.base_lab import LabWorker


class DeployerExisting(LabWorker):

    @staticmethod
    def sample_config():
        return {'hardware-lab-config': 'path to yaml which describes the lab'}

    def __init__(self, config):
        self._lab_cfg_path = config['hardware-lab-config']

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
        from lab.laboratory import Laboratory
        from lab.cloud.openstack import OS

        if not clouds_and_servers['servers']:
            pod = Laboratory(cfg_or_path=self._lab_cfg_path)
            clouds_and_servers['servers'].append(pod.mgmt)
            clouds_and_servers['servers'].extend(pod.controls)
            clouds_and_servers['servers'].extend(pod.computes)

        director = clouds_and_servers['servers'][0]

        openrc_path = None
        openrc_body = None
        for path in ['/root/openstack-configs/openrc', '/home/stack/overcloudrc', '/root/keystonerc_admin']:
            ans = director.exe(command='cat {}'.format(path), is_warn_only=True)
            if 'No such file or directory' not in ans:
                openrc_body = ans
                openrc_path = path
                break

        if openrc_path is None:
            raise RuntimeError('{}: lab {} does not contain any valid cloud'.format(self, self._lab_cfg_path))

        return OS(name=self._lab_cfg_path.replace('.yaml', ''), mediator=director, openrc_path=openrc_path, openrc_body=openrc_body)

    def execute(self, servers):
        cloud = self.deploy_cloud(servers)
        return cloud
