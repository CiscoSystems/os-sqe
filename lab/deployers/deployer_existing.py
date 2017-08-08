from lab.base_lab import LabWorker


class DeployerExisting(LabWorker):

    @staticmethod
    def sample_config():
        return '1.2.3.4'

    def __init__(self, ip):
        from lab.laboratory import Laboratory
        self.pod = Laboratory.create_from_remote(ip=ip)

    @staticmethod
    def _its_ospd_installation(lab, list_of_servers):
        import re

        director = lab.mgm

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
            ans = mgm.exe(cmd='sudo ls {}'.format(path), is_warn_only=True)
            if 'No such file or directory' not in ans:
                openrc_path = path
                break

        if openrc_path is None:
            raise RuntimeError('{}: "{}" does not contain any valid cloud'.format(self, self.pod))
        mgm.exe(cmd='rm -f openrc && sudo cp {} openrc && sudo chown sqe.sqe openrc'.format(openrc_path), is_as_sqe=True)
        return OS(name=self.pod, mediator=mgm, openrc_path='openrc')

    def execute(self, clouds_and_servers):
        cloud = self.deploy_cloud(clouds_and_servers=clouds_and_servers)
        return cloud

if __name__ == '__main__':
    d = DeployerExisting('g7-2')
    d.execute({'clouds': [], 'servers': []})
