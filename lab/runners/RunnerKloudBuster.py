from lab.runners import Runner


class RunnerKloudBuster(Runner):

    def sample_config(self):
        return {'cloud': 'cloud name'}

    def __init__(self, config):
        super(RunnerKloudBuster, self).__init__(config=config)
        self.cloud_name = config['cloud']

    def execute(self, clouds, servers):
        cloud = clouds[0]
        open_rc = cloud.create_open_rc()
        open_rc_path = '/tmp/{0}.openrc'.format(self.cloud_name)
        results_path = '/tmp/{0}_results.json'.format(self.cloud_name)
        with open(open_rc_path, 'w') as f:
            f.write(open_rc)

        local_repo_dir = self.clone_repo(repo_url='https://github.com/openstack/kloudbuster.git', local_repo_dir='/tmp/kloudbuster')
        self.run(command='virtualenv .venv', in_directory=local_repo_dir)
        self.run(command='.venv/bin/pip install -r requirements.txt', in_directory=local_repo_dir)
        self.run(command='.venv/bin/python setup.py install', in_directory=local_repo_dir)
        self.run(command='.venv/bin/kloudbuster --tested-rc {0} --tested-passwd {1} --json {2}'.format(open_rc_path, cloud.password, results_path))
