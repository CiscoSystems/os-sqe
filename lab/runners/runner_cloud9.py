from lab.runners import Runner


class RunnerCloud9(Runner):

    def sample_config(self):
        return {'yaml-path': 'yaml path'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(RunnerCloud9, self).__init__(config=config)

        self.lab = Laboratory(config_path=config['yaml-path'])
        self.director = self.lab.director()

    # def __assign_ip_to_user_nic(self, undercloud):
    #     ssh = 'ssh -o StrictHostKeyChecking=no heat-admin@'
    #     for server in self.lab.computes():
    #         line = self.director.run(command='source {rc} && nova list | grep {name}'.format(rc=undercloud, name=server.name()))
    #         pxe_ip = line.split('=')[-1].replace(' |', '')
    #         line = self.director.run("{s}{pxe_ip} /usr/sbin/ip -o l | awk '/:aa:/ {{print $2}}'".format(s=ssh, pxe_ip=pxe_ip))
    #         user_if = line.split('\n')[-1].strip(':')
    #         self.director.run('{s}{pxe_ip} sudo ip a flush dev {user_if}'.format(s=ssh, pxe_ip=pxe_ip, user_if=user_if))
    #         self.director.run('{s}{pxe_ip} sudo ip a a {user_ip}/{bits} dev {user_if}'.format(s=ssh, pxe_ip=pxe_ip, user_if=user_if, user_ip=server.ip, bits=server.net.prefixlen))
    #         self.director.run('{s}{pxe_ip} sudo ip r r default via {user_gw} dev {user_if}'.format(s=ssh, pxe_ip=pxe_ip, user_gw=self.lab.user_gw, user_if=user_if))
    #     for server in self.lab.all_but_director():
    #         self.director.run('{s}{ip} \'echo "{public}" >> .ssh/authorized_keys\''.format(s=ssh, ip=server.ip, public=self.lab.public_key))

    def __copy_stack_files(self, user):
        self.director.exe(command='sudo cp /home/stack/overcloudrc .')
        self.director.exe(command='sudo cp /home/stack/stackrc .')
        self.director.exe(command='sudo cp /home/stack/.ssh/id_rsa* .', in_directory='.ssh')
        self.director.exe(command='sudo chown {0}.{0} overcloudrc stackrc .ssh/*'.format(user))
        self.director.exe(command='cat id_rsa.pub >> authorized_keys', in_directory='.ssh')
        return '~/overcloudrc', '~/stackrc'

    def __prepare_sqe_repo(self):
        import os

        self.director.check_or_install_packages(package_names='python-virtualenv')

        sqe_repo = self.director.clone_repo(repo_url='https://github.com/cisco-openstack/openstack-sqe.git')
        sqe_venv = os.path.join('~/VE', os.path.basename(sqe_repo))
        self.director.exe(command='virtualenv {0}'.format(sqe_venv))
        self.director.exe(command='{0}/bin/pip install -r requirements.txt'.format(sqe_venv), in_directory=sqe_repo)
        return sqe_repo

    def __create_bashrc(self, sqe_repo):
        self.director.exe(command='rm -f ~/.bashrc')
        self.director.exe(command='ln -s {0}/configs/bashrc ~/.bashrc'.format(sqe_repo))

    def __install_filebeat(self):
        for server in self.lab.controllers():
            filebeat_config_body = '''
filebeat:
  prospectors:
    -
      paths:
        - /var/log/neutron/server.log
      input_type: log
      document_type: {document_type}
output:
  logstash:
    hosts: ["{logstash}"]
'''.format(logstash=self.lab.logstash_creds(), document_type=server.actuate_hostname())

            filebeat = 'filebeat-1.0.0-x86_64.rpm'
            server.exe(command='curl -L -O http://172.29.173.233/{0}'.format(filebeat))
            server.exe(command='sudo rpm --force -vi {0}'.format(filebeat))
            server.r_put_string_as_file_in_dir(string_to_put=filebeat_config_body, file_name='filebeat.yml', in_directory='/etc/filebeat')
            server.exe(command='sudo /etc/init.d/filebeat restart')
            server.exe(command='sudo /etc/init.d/filebeat status')

    def enable_neutron_debug_verbose(self):
        for server in self.lab.controllers():
            server.exe("sed -i 's/^verbose = False/verbose = True/g' /etc/neutron/neutron.conf")
            server.exe("sed -i 's/^debug = False/debug = True/g' /etc/neutron/neutron.conf")
            server.exe("systemctl restart neutron-server")

    def run_on_director(self):
        user = 'sqe'
        self.director.exe(command='sudo rm -f /home/{0}/.bashrc'.format(user), warn_only=True)
        self.director.r_create_user(new_username=user)

        overcloud, undercloud = self.__copy_stack_files(user=user)

        self.director.exe(command='ssh -o StrictHostKeyChecking=no localhost hostname')

        # self.__assign_ip_to_user_nic(undercloud=undercloud)
        self.__install_filebeat()
        self.enable_neutron_debug_verbose()
        undercloud_nodes = self.director.exe(command='source {0} && nova list'.format(undercloud))

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
        return True


if __name__ == '__main__':
    r = RunnerCloud9(config={'yaml-path': 'configs/g10.yaml'})
    r.run_on_director()
