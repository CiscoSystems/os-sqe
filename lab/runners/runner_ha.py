from lab.base_lab import LabWorker


def starter(worker):
    return worker.start_worker()


class RunnerHA(LabWorker):
    MODE_CHECK = 'check'
    MODE_RUN = 'run'
    MODE_DEBUG = 'debug'

    @staticmethod
    def sample_config():
        return {'task-yaml': 'task-ha.yaml', 'mode': 'run'}

    def __init__(self, config):
        self._task_yaml_path = config['task-yaml']
        self._task_body = self.read_config_from_file(config_path=self._task_yaml_path, directory='ha')
        self._mode = config['mode']

        if not self._task_body:
            raise Exception('Empty Test task list. Please check the file: {0}'.format(self._task_yaml_path))

    def execute(self, cloud):
        import multiprocessing
        import fabric.network

        manager = multiprocessing.Manager()
        shared_dict = manager.dict()
        shared_dict['cloud'] = cloud
        shared_dict['lab'] = cloud.get_lab()
        shared_dict['yaml-path'] = self._task_yaml_path
        shared_dict['is-debug'] = self._mode == self.MODE_DEBUG

        self.add_all_workers_to_shared_dict(shared_dict)

        workers = self.initialize_workers(shared_dict=shared_dict)

        fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing

        pool = multiprocessing.Pool(len(workers))
        return pool.map(starter, workers)

    def add_all_workers_to_shared_dict(self, shared_dict):
        for desc in self._task_body:
            if 'class' not in desc:
                continue
            try:
                name = desc['name']
            except KeyError:
                raise ValueError('{} in {} should define "name"'.format(desc['class'], self._task_yaml_path))
            if name in shared_dict:
                raise ValueError('{} in {} defines name "{}" which is already defined'.format(desc['class'], self._task_yaml_path, name))
            shared_dict[name] = desc

    def initialize_workers(self, shared_dict):
        import importlib

        workers = []
        for name, desc in shared_dict.items():
            if type(desc) is not dict:
                continue
            path_to_module, class_name = desc['class'].rsplit('.', 1)

            try:
                module = importlib.import_module(path_to_module)
            except ImportError:
                raise ValueError('{}: tries to run {}.py which does not exist'.format(self._task_yaml_path, path_to_module))
            try:
                klass = getattr(module, class_name)
            except AttributeError:
                raise ValueError('Please create class {} in {}.py'.format(class_name, path_to_module))
            workers.append(klass(shared_dict=shared_dict, name=name))
        return workers

    @staticmethod
    def run(lab_cfg_path, test_regex, mode):
        import time
        from lab.deployers.deployer_existing import DeployerExisting
        from lab.tims import Tims
        from lab.elk import Elk

        available_tc = RunnerHA.ls_configs(directory='ha')
        tests = sorted(filter(lambda x: test_regex in x, available_tc))

        if not tests:
            raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

        RunnerHA.check_config()
        if mode == RunnerHA.MODE_CHECK:
            return

        deployer = DeployerExisting(config={'hardware-lab-config': lab_cfg_path})
        cloud = deployer.execute([])
        if len(cloud.get_computes()) < 2:
            raise RuntimeError('{}: not possible to run on this cloud, number of compute hosts less then 2'.format(lab_cfg_path))

        mercury_version, vts_version = cloud.get_lab().r_get_version()

        tims = Tims()
        exceptions = []

        for tst in tests:
            start_time = time.time()
            runner = RunnerHA(config={'task-yaml': tst, 'mode': mode})
            results = runner.execute(cloud)

            elk = Elk(proxy=cloud.get_mediator())
            elk.filter_error_warning_in_last_seconds(seconds=time.time() - start_time)
            tims.publish_result(test_cfg_path=tst, mercury_version=mercury_version, lab=cloud.get_lab(), results=results)
            exceptions = reduce(lambda l, x: l + x['exceptions'], results, exceptions)

        if exceptions:
            raise RuntimeError('Possible reason: {}'.format(exceptions))

    @staticmethod
    def check_config():
        for tst in RunnerHA.ls_configs(directory='ha'):
            r = RunnerHA(config={'task-yaml': tst, 'mode': RunnerHA.MODE_CHECK})
            shared_dict = {}
            r.add_all_workers_to_shared_dict(shared_dict)
            r.initialize_workers(shared_dict)
