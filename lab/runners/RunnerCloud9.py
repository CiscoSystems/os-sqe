from lab.runners import Runner


class RunnerCloud9(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name', 'task-yaml': 'path to the valid task yaml file'}

    def __init__(self, config):
        pass

    def __assign_ip_to_user_nic(self):
        for line in self.director_server.run(command='source stackrc && nova list').split('\n'):
            ip_on_pxe_int = line
            iface_on_user = self.director_server.run("ssh heat-admin@{ip_on_pxe_int} /usr/sbin/ip -o l | awk '/:aa:/ {print $2}'".format(ip_on_pxe_int=ip_on_pxe_int))
            iface_on_user.strip(':')
            self.director_server.run("ssh heat-admin@{ip_on_pxe_int} sudo ip a a 10.23.230.135/27 dev {iface_on_user}".format(ip_on_pxe_int=ip_on_pxe_int))

    def __copy_stack_files(self, server):
        server.run(command='sudo cp /home/stack/overcloudrc .')
        server.run(command='sudo cp /home/stack/stackrc .')
        server.run(command='sudo cp /home/stack/.ssh/id_rsa* .', in_directory='.ssh')
        server.run(command='sudo chown {0} *'.format(user))
        server.run(command='sudo chown {0} *'.format(user), in_directory='.ssh')
        return (server.run(command='ls ~/ovefcloudrc'), server.run(command='ls ~/stackrc'))

    def __prepare_sqe_repo(self, server):
        server.check_or_install_packages(package_names='xterm xauth')

        sqe_repo = server.clone_repo(repo_url='https://github.com/cisco-openstack/openstack-sqe.git')
        sqe_venv = '~/VE/sqe'
        server.run(command='virtualenv {0}'.format(sqe_venv))
        server.run(command='{0}/bin/pip install -r requirements.txt'.format(sqe_venv), in_directory=sqe_repo)
        return (sqe_repo, server.run(command='ls {0}'.format(sqe_venv)))

    def __create_bashrc(self, server, undercloud, overcloud):
        bashrc = '''
[ -f /etc/bashrc ] &&  . /etc/bashrc

function venv()
{{
    local MY_ENV_DIR=~/VE
    local venv=$(basename $(pwd))
    [ -d ${{MY_ENV_DIR}}/${{venv}} ] || virtualenv ${{MY_VENV_DIR}}/${{venv}}
    . ${{MY_VENV_DIR}}/${{venv}}/bin/activate
    pip install -r requirements.txt
}}

function power-cycle()
{{
    local what=${{1}}

    source {undercloud}
    for uuid in $(nova list | grep ${{what}} | awk '{{print $2}}') ;  do
        node=$(ironic node-list | grep ${{uuid}} | awk '{{print $2}}')
        echo Re-booting ${{node}}
        ironic node-set-power-state ${{node}} reboot
    done
    ironic node-list
    source {overcloud}
    nova service-list
}}
'''.format(undercloud=undercloud, overcloud=overcloud)
        server.put_string_as_file_in_dir(string_to_put=bashrc, file_name='.bashrc')

    def run_on_director(self, director_ip):
        from lab.Server import Server

        director = Server(ip=director_ip, username='root', password='cisco123')

        user = 'sqe'
        director.run(command='sudo rm -f /home/{0}/.bashrc'.format(user), warn_only=True)
        director.create_user(new_username=user)


        overcloud, undercloud = self.__copy_stack_files(server=director)

        self.__assign_ip_to_user_nic()
        undercloud_nodes = director.run(command='source {0} && nova list'.format(undercloud))
        os_password = director.run(command='grep PASSWORD {0}'.format(cloud_rc_name)).split('=')[-1]


        config_yaml = '''
monitor: monitor_fi_vlan
monitor: monitor_n9k_vlan
load: networks
disruptor: fi_reboot
disruptor: n9k_reboot
'''
        role_ip = []
        counts = {'controller': 0, 'compute': 0}
        for line in undercloud_nodes.split('\n'):
            for role in ['controller', 'compute']:
                if role in line:
                    ip = line.split('=')[-1].replace(' |', '')
                    counts[role] += 1
                    role_ip.append('{role}-{n}:\n   ip: {ip}\n   user: heat-admin\n   password: ""\n   role: {role}'.format(role=role, n=counts[role], ip=ip))

        openstack_config_yaml = '\n\n'.join(role_ip) + '\n'


        director.put_string_as_file_in_dir(string_to_put=config_yaml, file_name='executor.yaml')

        #director.run(command='export PYTHONPATH=. && export HAPATH=. && {0}/bin/python ha_engine/ha_main.py -f configs/executor.yaml'.format(cloud99_venv), in_directory=cloud99_repo)

    def execute(self, clouds, servers):
        super(RunnerCloud9, self).execute(clouds, servers)


if __name__ == '__main__':
    r = RunnerCloud9('aaa')
    r.run_on_director('10.23.230.134')
