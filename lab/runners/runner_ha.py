from lab.runners import Runner


def starter(worker):
    worker.setup()
    return worker.start()


class RunnerHA(Runner):
    def sample_config(self):
        return {'cloud': 'cloud name', 'task-yaml': 'task-ha.yaml'}

    def __init__(self, config):
        super(RunnerHA, self).__init__(config=config)
        self._cloud_name = config['cloud']
        self._task_yaml_path = config['task-yaml']
        self._task_body = self.read_config_from_file(config_path=self._task_yaml_path, directory='ha')
        if not self._task_body:
            raise Exception('Empty Test task list. Please check the file: {0}'.format(self._task_yaml_path))

    def __repr__(self):
        import os

        return u'{0}-{1}'.format(self._cloud_name, os.path.basename(self._task_yaml_path))

    def execute(self, clouds, servers):
        import importlib
        import multiprocessing
        import fabric.network

        try:
            cloud = filter(lambda x: x.name == self._cloud_name, clouds)[0]
        except IndexError:
            raise RuntimeError('Cloud <{0}> is not provided by deployment phase'.format(self._cloud_name))

        workers_to_run = []
        path_to_module = 'Before reading task body'
        for arguments in self._task_body:
            try:
                path_to_module, class_name = arguments['class'].rsplit('.', 1)
                module = importlib.import_module(path_to_module)
                klass = getattr(module, class_name)
                workers_to_run.append(klass(cloud=cloud, **arguments))
            except KeyError:
                raise ValueError('There is no "class" specifying the worker class path in {0}'.format(self._task_yaml_path))
            except ImportError:
                raise ValueError('{0} failed to import'.format(path_to_module))

        fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing

        pool = multiprocessing.Pool(len(workers_to_run))

        return pool.map(starter, workers_to_run)
