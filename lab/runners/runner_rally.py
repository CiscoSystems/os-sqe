from lab.runners import Runner


class RunnerRally(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name', 'task-yaml': 'path to the valid task yaml file', 'rally-repo': 'http', 'rally-patch': ''}

    def __init__(self, config):
        from lab.with_config import read_config_from_file

        super(RunnerRally, self).__init__(config=config)
        self._cloud_name = config['cloud']
        self._task_body = read_config_from_file(yaml_path=config['task-yaml'], directory='artifacts', is_as_string=True)
        self._rally_repo = config['rally-repo']
        self._rally_patch = config['rally-patch']

    def execute(self, clouds, servers):
        import os

        cloud = filter(lambda x: x.name == self._cloud_name, clouds)
        if not cloud:
            raise RuntimeError('Cloud <{0}> is not provided by deployment phase'.format(self._cloud_name))

        server = servers[0] if servers else cloud[0].mediator
        open_rc_path = '{0}.openrc'.format(self._cloud_name)
        rally_html = 'rally-results.html'
        task_path = 'rally-task.yaml'
        venv_path = '~/venv_rally'
        patch_path = '/home/rally_scale_changes.patch'
        
        open_rc_body = cloud[0].create_open_rc()

        server.create_user(new_username='rally')
        server.put_string_as_file_in_dir(string_to_put=open_rc_body, file_name=open_rc_path)
        server.put_string_as_file_in_dir(string_to_put=self._task_body, file_name=task_path)

        rally_installed = True if server.exe(command='test -d rally', warn_only=True) else False

        if not rally_installed:
            repo_dir = server.clone_repo(repo_url=self._rally_repo, patch=self._rally_patch, tags='0.2.0')
            server.check_or_install_packages(package_names='libffi-devel gmp-devel postgresql-devel wget python-virtualenv')
            server.exe(command='git apply {0}'.format(patch_path), in_directory=repo_dir, warn_only=True)
            server.exe(command='./install_rally.sh -y -d {0}'.format(venv_path), in_directory=repo_dir)
            server.exe(command='source {0} && {1}/bin/rally deployment create --fromenv --name {2}'.format(open_rc_path, venv_path, self._cloud_name))

            rally_installed = True

        if rally_installed:
            server.exe(command='{0}/bin/rally task start {1}'.format(venv_path, task_path))
            server.exe(command='{0}/bin/rally task report --out {1}'.format(venv_path, rally_html))
            server.get(remote_path=rally_html, local_path=os.path.join(self.ARTIFACTS_DIR, rally_html))
