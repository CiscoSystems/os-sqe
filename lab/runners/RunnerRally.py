from lab.runners import Runner


class RunnerRally(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name', 'task-yaml': 'path to the valid task yaml file'}

    def __init__(self, config):
        from lab.WithConfig import read_config_from_file

        super(RunnerRally, self).__init__(config=config)
        self.cloud_name = config['cloud']
        self.task_yaml_path = config['task-yaml']
        self.task_body = read_config_from_file(yaml_path=self.task_yaml_path, directory='rally', is_as_string=True)

    def execute(self, clouds, servers):

        cloud = clouds[0]
        server = servers[0]
        open_rc_path = '{0}.openrc'.format(self.cloud_name)
        results_path = 'rally-results.html'
        task_path = 'rally-task.yaml'
        venv_path = '~/venv_rally'

        open_rc_body = cloud.create_open_rc()

        server.create_user(new_username='rally')
        server.put(string_to_put=open_rc_body, file_name=open_rc_path)
        server.put(string_to_put=self.task_body, file_name=task_path)

        repo_dir = server.clone_repo(repo_url='https://git.openstack.org/openstack/rally.git')
        server.check_or_install_packages(package_names='libffi-devel gmp-devel postgresql-devel wget python-virtualenv')
        server.run(command='./install_rally.sh -y -d {0}'.format(venv_path), in_directory=repo_dir)
        server.run(command='source {0} && {1}/bin/rally deployment create --fromenv --name {2}'.format(open_rc_path, venv_path, self.cloud_name))
        server.run(command='{0}/bin/rally task start {1}'.format(venv_path, task_path))
        server.run(command='{0}/bin/rally task report --out {1}'.format(venv_path, results_path))
        server.get(remote_path=results_path, local_path=results_path)
        self.get_artefacts(server=server)
