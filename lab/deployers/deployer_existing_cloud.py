from lab.base_lab import LabWorker


class DeployerExistingCloud(LabWorker):

    @staticmethod
    def sample_config():
        return '1.2.3.4'

    def __init__(self, lab_name, allowed_drivers):
        from lab.laboratory import Laboratory
        self.pod = Laboratory.create(lab_name=lab_name, allowed_drivers=allowed_drivers)

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
            clouds_and_servers['servers'].append(self.pod.mgm)
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
        cloud = OS(name=self.pod.name, mediator=mgm, openrc_path='openrc')
        cloud.os_all()
        return cloud

    def execute(self, clouds_and_servers):
        return self.deploy_cloud(clouds_and_servers=clouds_and_servers)
