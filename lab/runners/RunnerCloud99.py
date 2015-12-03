from lab.runners import Runner


class RunnerCloud99(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name', 'task-yaml': 'path to the valid task yaml file'}

    def __init__(self, config):
        pass

    def run_on_director(self, director_ip):
        from lab.Server import Server

        director = Server(ip=director_ip, username='root', password='cisco123')

        user = 'sqe'

        cloud_rc_name = '~/over-cloud-rc'
        rally_venv = '~/VE/rally'
        cloud99_venv = '~/VE/cloud99'

        node_list = director.run(command='source stackrc && nova list')

        director.run(command='sudo rm -f /home/{0}/.bashrc'.format(user), warn_only=True)

        director.create_user(new_username=user)

        director.run(command='sudo cp /home/stack/overcloudrc {0}'.format(cloud_rc_name))
        director.run(command='sudo cp /home/stack/stackrc ~/stackrc')
        director.run(command='sudo cp /home/stack/.ssh/id_rsa* .', in_directory='.ssh')
        director.run(command='sudo chown {0} id_rsa*'.format(user), in_directory='.ssh')

        rally_repo = director.clone_repo(repo_url='https://git.openstack.org/openstack/rally.git')
        director.check_or_install_packages(package_names='libffi-devel gmp-devel postgresql-devel wget python-virtualenv xterm xauth')
        director.run(command='./install_rally.sh -y -d {0}'.format(rally_venv), in_directory=rally_repo)
        director.run(command='source {0} && {1}/bin/rally deployment create --fromenv --name cloud'.format(cloud_rc_name, rally_venv))

        cloud99_repo = director.clone_repo(repo_url='https://github.com/cisco-oss-eng/Cloud99.git')
        director.run(command='virtualenv {0}'.format(cloud99_venv))
        director.run(command='{0}/bin/pip install -r requirements.txt'.format(cloud99_venv), in_directory=cloud99_repo)
        if not director.run(command='git remote -v | grep gitlab', in_directory=cloud99_repo, warn_only=True):
            director.run(command='git remote add gitlab http://gitlab.cisco.com/kshileev/cloud99.git', in_directory=cloud99_repo)

        director.run(command='git checkout -b nxos-ucsm gitlab/nxos-ucsm', in_directory=cloud99_repo)


        executor_yaml = '''
executors:
    -
        # infra parameters
        mode: parallel
        repeat: 1
        sync: true
        ha_interval:  30

        # disruption scenario
        execute: [cvd2_ha]

        monitor_vlans: [monitor_g10N9k9396PX1]
        monitor_users: [monitor_g10N9k9396PX2]
        monitor_ssh: [monitor_g10N9k9396PX2]
        monitor_allowed_vlans: [monitor_g10N9k9396PX2]

        #container_disruption: [nova_api_container]
'''

        monitors_yaml = '''
monitors:
    # Sample monitor template
    # <monitor_name>: (Depicts name of the backend plugin class under monitors/plugins)
    #     <monitor_ref>: (Depicts the logical name to be provided in executor.yaml
    #          <input_parameters> : (Consist of input parameters passed in to the monitor class)
    # Example config for nagios monitor
    # type: denotes monitoring openstack hosts vs applicationvm
    # Use keyword "openstackvm" to denote monitoring existing cloud resources.
    # List of floatingips for cloud resources in file appvmlist
    nagiosmonitor:
        nagios:
            type: openstackvm
    nagioscfgset:
        nagioscfg:

    # Example config for ansible host monitor
    # frequency: interval of polling
    # dockerized: set to True in container based installations
    # mariadb/user, mariadb/password: Specify correct values for your cloud

    ansiblemonitor:
        ansible:
            loglevel: ERROR
            frequency: 5
            max_hist: 25
            sudo: False
            dockerized: True
            mariadb:
              user: root
              password: qBfDS1CiaKUn4pIl


    # Example config for Openstack endpoint and service monitor
    # openrc_file and password: Specify pointer to openrc credentials or source openrc before running script
    healthapi:
        openstack_api:
            openrc_file: {0}
            password: 7ece5c821b6c2b1c888c58f59867f7a09be40c69
            frequency: 5
            max_entries: 20

'''.format(cloud_rc_name)

        role_ip = []
        counts = {'controller': 0, 'compute': 0}
        for line in node_list.split('\n'):
            for role in ['controller', 'compute']:
                if role in line:
                    ip = line.split('=')[-1].replace(' |', '')
                    counts[role] += 1
                    role_ip.append('{role}-{n}:\n   ip: {ip}\n   user: heat-admin\n   password: ""\n   role: {role}'.format(role=role, n=counts[role], ip=ip))

        openstack_config_yaml = '\n\n'.join(role_ip) + '\n'

        runner_yaml = '''
runners:
   # Sample runner file
   # <runner_name>: (Name of backend plugin class for runner in runners/plugins)
   #    <runner_ref>: (Logical name for runner test specified in executor.yaml)
   #        <input_parameters> : (Input parameters passed to the runner class)
    rally:
        # Rally boot test
        neutron_test:
            scenario_name: neutron
            rally_path:  {rally_venv}/bin/rally
            scenario_file: {cloud99_repo}/configs/scenarios/neutron_create_and_list_ports.json
'''.format(rally_venv=rally_venv, cloud99_repo=cloud99_repo)

        director.put_string_as_file_in_dir(string_to_put=executor_yaml, file_name='executor.yaml', in_directory='{0}/configs'.format(cloud99_repo))
        director.put_string_as_file_in_dir(string_to_put=monitors_yaml, file_name='monitors.yaml', in_directory='{0}/configs'.format(cloud99_repo))
        director.put_string_as_file_in_dir(string_to_put=openstack_config_yaml, file_name='openstack_config.yaml', in_directory='{0}/configs'.format(cloud99_repo))
        director.put_string_as_file_in_dir(string_to_put=runner_yaml, file_name='runners.yaml', in_directory='{0}/configs'.format(cloud99_repo))

        #director.run(command='export PYTHONPATH=. && export HAPATH=. && {0}/bin/python ha_engine/ha_main.py -f configs/executor.yaml'.format(cloud99_venv), in_directory=cloud99_repo)

        bashrc = '''
[ -f /etc/bashrc ] &&  . /etc/bashrc

source {cloud99_venv}/bin/activate
cd {cloud99_repo}
source install.sh
alias c='cd {cloud99_repo} && python ha_engine/ha_main.py -f configs/executor.yaml'
alias venv_cloud99='source {cloud99_venv}/bin/activate'
alias venv_rally='source {rally_venv}/bin/activate'

function power-cycle(){{
    local what=${{1}}

    source ~/stackrc
    for uuid in $(nova list | grep ${{what}} | awk '{{print $2}}') ;  do
        node=$(ironic node-list | grep ${{uuid}} | awk '{{print $2}}')
        echo Re-booting ${{node}}
        ironic node-set-power-state ${{node}} reboot
    done
    ironic node-list
    source {cloud_rc}
    nova service-list
}}

export RALLY_PLUGIN_PATHS={cloud99_repo}/rally_plugins
'''.format(cloud99_venv=cloud99_venv, cloud99_repo=cloud99_repo, rally_venv=rally_venv, cloud_rc=cloud_rc_name)

        director.put_string_as_file_in_dir(string_to_put=bashrc, file_name='.bashrc')

    def execute(self, clouds, servers):
        super(RunnerCloud99, self).execute(clouds, servers)


if __name__ == '__main__':
    r = RunnerCloud99('aaa')
    r.run_on_director('10.23.230.134')
