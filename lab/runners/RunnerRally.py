from lab.runners import Runner


class RunnerRally(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name'}

    def __init__(self, config):
        super(RunnerRally, self).__init__(config=config)
        self.cloud_name = config['cloud']

    def execute(self, clouds, servers):
        cloud = clouds[0]
        open_rc_path = '{0}.openrc'.format(self.cloud_name)
        results_path = '{0}_rally_results.html'.format(self.cloud_name)
        task_path = '{0}_rally_task.yaml'.format(self.cloud_name)
        venv_path = '~/rally_venv'

        open_rc_body = cloud.create_open_rc()
        with open('lab/configs/rally/scaling.yaml') as f:
            task_body = f.read()

        self.create_user(new_username='rally', server=servers[0])
        self.put(what=open_rc_body, name=open_rc_path, server=servers[0])
        self.put(what=task_body, name=task_path, server=servers[0])

        local_repo_dir = self.clone_repo(repo_url='https://git.openstack.org/openstack/rally.git', server=servers[0])
        self.check_or_install_packages(package_names='libffi-devel gmp-devel postgresql-devel wget python-virtualenv', server=servers[0])
        self.run(command='./install_rally.sh -d {0}'.format(venv_path), in_directory=local_repo_dir, server=servers[0])
        self.run(command='source {0} && {1}/bin/rally deployment create --fromenv --name {2}'.format(open_rc_path, venv_path, self.cloud_name), server=servers[0])
        self.run(command='{0}/bin/rally task start {1}'.format(venv_path, task_path), server=servers[0])
        self.run(command='{0}/bin/rally task report --output {1}'.format(venv_path, results_path), server=servers[0])
