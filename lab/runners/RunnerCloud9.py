from lab.runners import Runner


class RunnerCloud9(Runner):

    def sample_config(self):
        return {'yaml-path': 'yaml path'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(RunnerCloud9, self).__init__(config=config)

        self.lab = Laboratory(config_path=config['yaml-path'])
        self.director = self.lab.director()

    def __assign_ip_to_user_nic(self, undercloud):
        from lab.Server import Server

        ssh = 'ssh -o StrictHostKeyChecking=no heat-admin@'
        servers = []
        for role, ip in self.lab.all_but_director():
            line = self.director.run(command='source {0} && nova list | grep -P "{1}.*?\-{2}"'.format(undercloud, role))
            for i, user_ip in enumerate():
                pxe_ip = line.split('=')[-1].replace(' |', '')
                line = self.director.run("{s}{pxe_ip} /usr/sbin/ip -o l | awk '/:aa:/ {{print $2}}'".format(s=ssh, pxe_ip=pxe_ip))
                user_if = line.split('\n')[-1].strip(':')
                self.director.run('{s}{pxe_ip} sudo ip a flush dev {user_if}'.format(s=ssh, pxe_ip=pxe_ip, user_if=user_if))
                self.director.run('{s}{pxe_ip} sudo ip a a {user_ip} dev {user_if}'.format(s=ssh, pxe_ip=pxe_ip, user_if=user_if, user_ip=user_ip))
                self.director.run('{s}{pxe_ip} sudo ip r r default via {user_gw} dev {user_if}'.format(s=ssh, pxe_ip=pxe_ip, user_gw=self.lab.gw, user_if=user_if))

                self.director.run('{s}{pxe_ip} \'echo "{public}" >> .ssh/authorized_keys\''.format(s=ssh, pxe_ip=pxe_ip, public=self.lab.public_key()))
                servers.append(Server(ip=user_ip.split('/')[0], role=role, username='heat-admin'))
        return servers

    def __copy_stack_files(self, user):
        self.director.run(command='sudo cp /home/stack/overcloudrc .')
        self.director.run(command='sudo cp /home/stack/stackrc .')
        self.director.run(command='sudo cp /home/stack/.ssh/id_rsa* .', in_directory='.ssh')
        self.director.run(command='sudo chown {0}.{0} overcloudrc stackrc .ssh/*'.format(user))
        self.director.run(command='cat id_rsa.pub >> authorized_keys', in_directory='.ssh')
        return '~/overcloudrc', '~/stackrc'

    def __prepare_sqe_repo(self):
        import os

        self.director.check_or_install_packages(package_names='xterm xauth libvirt')

        sqe_repo = self.director.clone_repo(repo_url='https://github.com/cisco-openstack/openstack-sqe.git')
        sqe_venv = os.path.join('~/VE', os.path.basename(sqe_repo))
        self.director.run(command='virtualenv {0}'.format(sqe_venv))
        self.director.run(command='{0}/bin/pip install -r requirements.txt'.format(sqe_venv), in_directory=sqe_repo)
        return sqe_repo

    def __create_bashrc(self, sqe_repo):
        self.director.run(command='rm -f ~/.bashrc')
        self.director.run(command='ln -s {0}/configs/bashrc ~/.bashrc'.format(sqe_repo))

    @staticmethod
    def __install_filebeat(servers):
        filebeat_config_body = '''
filebeat:
  prospectors:
    -
      paths:
        - /var/log/neutron/server.log
output:
  logstash:
    hosts: ["172.29.173.236:5044"]
'''
        for server in servers:
            if server.role.startswith('control'):
                server.run(command='curl -L -O http://172.29.173.233/filebeat-1.0.0-x86_64.rpm')
                server.run(command='sudo rpm -vi filebeat-1.0.0-x86_64.rpm')
                server.put_string_as_file_in_dir(string_to_put=filebeat_config_body, file_name='filebeat.yml', in_directory='/etc/filebeat')

    def run_on_director(self):
        user = 'sqe'
        self.director.run(command='sudo rm -f /home/{0}/.bashrc'.format(user), warn_only=True)
        self.director.create_user(new_username=user)

        overcloud, undercloud = self.__copy_stack_files(user=user)

        self.director.run(command='ssh -o StrictHostKeyChecking=no localhost hostname')

        servers = self.__assign_ip_to_user_nic(undercloud=undercloud)
        self.__install_filebeat(servers=servers)
        undercloud_nodes = self.director.run(command='source {0} && nova list'.format(undercloud))

        role_ip = []
        counts = {'controller': 0, 'compute': 0}
        for line in undercloud_nodes.split('\n'):
            for role in ['controller', 'compute']:
                if role in line:
                    ip = line.split('=')[-1].replace(' |', '')
                    counts[role] += 1
                    role_ip.append('{role}-{n}:\n   ip: {ip}\n   user: heat-admin\n   password: ""\n   role: {role}'.format(role=role, n=counts[role], ip=ip))

        sqe_repo = self.__prepare_sqe_repo()
        self.__create_bashrc(sqe_repo=sqe_repo)

    def execute(self, clouds, servers):
        super(RunnerCloud9, self).execute(clouds, servers)


if __name__ == '__main__':
    r = RunnerCloud9(config={'yaml-path': 'lab/configs/labs/g10.yaml'})
    r.run_on_director()
