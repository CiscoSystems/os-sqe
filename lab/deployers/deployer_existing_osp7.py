from lab.deployers import Deployer


class DeployerExistingOSP7(Deployer):

    def sample_config(self):
        return {'cloud': 'arbitrary name', 'hardware-lab-config': 'some of existing hardware lab description'}

    def __init__(self, config):
        super(DeployerExistingOSP7, self).__init__(config=config)
        self.lab_cfg = config['hardware-lab-config']
        self.cloud_name = config['cloud']

    @staticmethod
    def get_deployment_info(director):
        import json
        import lab

        body = director.get_file_from_dir('osp_install_run.json', '/etc')
        lab.OSP7_INFO = json.loads(body)

    def deploy_cloud(self, list_of_servers):
        from lab.cloud import Cloud
        from lab.laboratory import Laboratory
        from lab.server import Server
        import re

        if list_of_servers:
            director = list_of_servers[0]
        else:
            director = Laboratory(config_path=self.lab_cfg).get_director()

        list_of_servers.append(director)
        self.get_deployment_info(director=director)

        net = director.lab().get_ssh_net()
        ssh_ip_pattern = '({0}.*)/{1}'.format(str(net).rsplit('.', 1)[0], net.prefixlen)
        re_ip = re.compile(ssh_ip_pattern)
        lines = director.run('source stackrc && nova list').split('\n')
        for line in lines:
            if '=' in line:
                local_ip = line.split('=')[-1].split()[0]
                name = line.split('|')[2]
                ip_a_ans = director.run('ssh -o StrictHostKeyChecking=no {local_ip} ip -o a'.format(local_ip=local_ip))
                ip = re_ip.findall(ip_a_ans)
                if ip:
                    list_of_servers.append(Server(name=name, username='root', lab=director.lab(), ip=ip[0]))

        overcloud_openrc = director.run(command='cat /home/stack/overcloudrc')
        return Cloud.from_openrc(name=self.cloud_name, mediator=director, openrc_as_string=overcloud_openrc)

    def wait_for_cloud(self, list_of_servers):
        cloud = self.deploy_cloud(list_of_servers)
        return cloud.verify_cloud()
