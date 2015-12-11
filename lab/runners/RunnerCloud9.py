from lab.runners import Runner


class RunnerCloud9(Runner):

    def sample_config(self):
        return {'yaml_path': 'yaml path'}

    def __init__(self, config):
        from netaddr import IPNetwork
        from lab.Server import Server
        from lab.WithConfig import read_config_from_file

        super(RunnerCloud9, self).__init__(config=config)

        lab_cfg = read_config_from_file(yaml_path=config['yaml_path'])
        user_net = IPNetwork(lab_cfg['nets']['user']['cidr'])
        self.director = Server(ip=str(user_net[lab_cfg['nodes']['director']['ip-shift'][0]]), username='root', password='cisco123')
        self.ips_on_user = {}
        self.gw_on_user = str(user_net[1])
        for role in ['ceph', 'control', 'compute']:
            self.ips_on_user[role] = [str(user_net[x]) + '/' + str(user_net.prefixlen) for x in lab_cfg['nodes'][role]['ip-shift']]

    def __assign_ip_to_user_nic(self, undercloud):
        ssh = 'ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no heat-admin@'
        for role, ips in self.ips_on_user.iteritems():
            for i, ip_on_user in enumerate(ips):
                line = self.director.run(command='source {0} && nova list | grep {1} | grep "\-{2}"'.format(undercloud, role, i))
                ip_on_pxe = line.split('=')[-1].replace(' |', '')
                line = self.director.run("{s}{ip_on_pxe} /usr/sbin/ip -o l | awk '/:aa:/ {{print $2}}'".format(s=ssh, ip_on_pxe=ip_on_pxe))
                if_on_user = line.split('\n')[-1].strip(':')
                self.director.run('{s}{ip_on_pxe} sudo ip a flush dev {iface_on_user}'.format(s=ssh, ip_on_pxe=ip_on_pxe, iface_on_user=if_on_user))
                self.director.run('{s}{ip_on_pxe} sudo ip a a {ip_on_user} dev {if_on_user}'.format(s=ssh, ip_on_pxe=ip_on_pxe, if_on_user=if_on_user, ip_on_user=ip_on_user))
                self.director.run('{s}{ip_on_pxe} sudo ip r r default via {gw_on_user} dev {if_on_user}'.format(s=ssh, ip_on_pxe=ip_on_pxe, gw_on_user=self.gw_on_user, if_on_user=if_on_user))

    def __copy_stack_files(self, user):
        self.director.run(command='sudo cp /home/stack/overcloudrc .')
        self.director.run(command='sudo cp /home/stack/stackrc .')
        self.director.run(command='sudo cp /home/stack/.ssh/id_rsa* .', in_directory='.ssh')
        self.director.run(command='sudo chown {0}.{0} overcloudrc stackrc .ssh/*'.format(user))
        return '~/overcloudrc', '~/stackrc'

    def __prepare_sqe_repo(self):
        import os

        self.director.check_or_install_packages(package_names='xterm xauth libvirt')

        sqe_repo = self.director.clone_repo(repo_url='https://github.com/cisco-openstack/openstack-sqe.git')
        sqe_venv = os.path.join('~/VE', os.path.basename(sqe_repo))
        self.director.run(command='virtualenv {0}'.format(sqe_venv))
        self.director.run(command='{0}/bin/pip install -r requirements.txt'.format(sqe_venv), in_directory=sqe_repo)
        return sqe_repo, self.director.run(command='ls {0}'.format(sqe_venv))

    def __create_bashrc(self, undercloud, overcloud):
        bashrc = '''
[ -f /etc/bashrc ] &&  . /etc/bashrc

function venv()
{{
    [ ! -d .git ] && echo "It's not git repo! aborting" && return
    local MY_VENV_DIR=~/VE
    local venv=$(basename $(pwd))
    [ -d ${{MY_VENV_DIR}}/${{venv}} ] || virtualenv ${{MY_VENV_DIR}}/${{venv}}
    . ${{MY_VENV_DIR}}/${{venv}}/bin/activate
    [ -f requirements.txt ] && pip install -r requirements.txt
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
        self.director.put_string_as_file_in_dir(string_to_put=bashrc, file_name='.bashrc')

    def run_on_director(self):
        user = 'sqe'
        self.director.run(command='sudo rm -f /home/{0}/.bashrc'.format(user), warn_only=True)
        self.director.create_user(new_username=user)

        overcloud, undercloud = self.__copy_stack_files(user=user)

        self.__assign_ip_to_user_nic(undercloud=undercloud)
        undercloud_nodes = self.director.run(command='source {0} && nova list'.format(undercloud))
        os_password = self.director.run(command='grep PASSWORD {0}'.format(overcloud)).split('=')[-1]

        config_yaml = '''
monitor_fi_vlan
monitor_n9k_vlan
networks
fi_reboot
n9k_reboot
'''
        role_ip = []
        counts = {'controller': 0, 'compute': 0}
        for line in undercloud_nodes.split('\n'):
            for role in ['controller', 'compute']:
                if role in line:
                    ip = line.split('=')[-1].replace(' |', '')
                    counts[role] += 1
                    role_ip.append('{role}-{n}:\n   ip: {ip}\n   user: heat-admin\n   password: ""\n   role: {role}'.format(role=role, n=counts[role], ip=ip))

        self.director.put_string_as_file_in_dir(string_to_put=config_yaml, file_name='ha.yaml')
        self.__prepare_sqe_repo()
        self.__create_bashrc(undercloud=undercloud, overcloud=overcloud)

    def execute(self, clouds, servers):
        super(RunnerCloud9, self).execute(clouds, servers)


if __name__ == '__main__':
    r = RunnerCloud9(config={'yaml_path': 'lab/configs/labs/g10.yaml'})
    r.run_on_director()
