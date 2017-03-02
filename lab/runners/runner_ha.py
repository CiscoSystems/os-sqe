from lab.base_lab import LabWorker
from lab import decorators


def starter(worker):
    return worker.start_worker()


class RunnerHA(LabWorker):

    @staticmethod
    def sample_config():
        return {'cloud-name': 'name', 'task-yaml': 'task-ha.yaml', 'is-debug': False, 'is-parallel': True}

    def __init__(self, config):
        self._task_yaml_path = config['task-yaml']
        self._task_body = self.read_config_from_file(config_path=self._task_yaml_path, directory='ha')
        self._is_debug = config['is-debug']
        self._is_parallel = config['is-parallel']

        if not self._task_body:
            raise Exception('Empty Test task list. Please check the file: {0}'.format(self._task_yaml_path))

    def execute(self, cloud):
        import importlib
        import multiprocessing
        import fabric.network

        manager = multiprocessing.Manager()
        shared_dict = manager.dict()

        type_of_run = ' {} {} debug in {}'.format(self._task_yaml_path, 'with' if self._is_debug else 'without', 'parallel' if self._is_parallel else 'sequence')
        self.log('Running ' + type_of_run)

        klass_kwargs = []
        for single_worker_description in self._task_body:
            if 'class' not in single_worker_description:
                continue
            path_to_module, class_name = single_worker_description['class'].rsplit('.', 1)
            try:
                module = importlib.import_module(path_to_module)
            except ImportError:
                raise ValueError('Please create {}.py'.format(path_to_module))
            try:
                klass = getattr(module, class_name)
            except AttributeError:
                raise ValueError('Please create class {} in {}.py'.format(class_name, path_to_module))
            single_worker_description['yaml_path'] = self._task_yaml_path
            shared_dict[class_name] = False

            klass_kwargs.append((klass, single_worker_description))

        workers_to_run = [klass(cloud=cloud, shared_dict=shared_dict, is_debug=self._is_debug, **kwargs) for klass, kwargs in klass_kwargs]

        fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing

        if self._is_parallel:
            pool = multiprocessing.Pool(len(workers_to_run))
            results = pool.map(starter, workers_to_run)  # a list of {'name': 'monitor, scenario or disruptor name', 'success': True or False, 'n_exceptions': 10}
        else:
            results = map(starter, workers_to_run)
        return results

    @decorators.section('reporting to TIMS and SLACK')
    def publish_to_tims(self, lab, results):
        from lab.tims import Tims

        t = Tims()
        mercury_version, vts_version = lab.r_get_version()
        t.publish_result(test_cfg_path=self._task_yaml_path, mercury_version=mercury_version, lab=lab, results=results)
