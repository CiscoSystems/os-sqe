from lab.base_lab import LabWorker


def starter(worker):
    return worker.start_worker()


class RunnerHA(LabWorker):
    def sample_config(self):
        return {'cloud': 'name', 'task-yaml': 'task-ha.yaml', 'is-debug': False, 'is-parallel': True, 'is-report-to-tims': True}

    def __init__(self, config, version):
        super(RunnerHA, self).__init__(config=config)
        self._cloud_name = config['cloud']
        self._task_yaml_path = config['task-yaml']
        self._task_body = self.read_config_from_file(config_path=self._task_yaml_path, directory='ha')
        self._is_debug = config['is-debug']
        self._is_parallel = config['is-parallel']
        self._is_report_to_tims = config['is-report-to-tims']
        self._version = version

        if not self._task_body:
            raise Exception('Empty Test task list. Please check the file: {0}'.format(self._task_yaml_path))

    def execute(self, servers_and_clouds):
        from lab.tims import Tims
        import importlib
        import multiprocessing
        import fabric.network

        try:
            cloud = filter(lambda x: x.get_name() == self._cloud_name, servers_and_clouds['clouds'])[0]
            lab = servers_and_clouds['servers'][0].lab()
        except IndexError:
            raise RuntimeError('Cloud <{0}> is not provided by deployment phase'.format(self._cloud_name))

        type_of_run = ' {} {} debug in {}'.format(self._task_yaml_path, 'with' if self._is_debug else 'without', 'parallel' if self._is_parallel else 'sequence')
        self.log('Running ' + type_of_run)

        workers_to_run = []
        path_to_module = 'Before reading task body'
        for block in self._task_body:
            try:
                if 'class' not in block:
                    continue
                path_to_module, class_name = block['class'].rsplit('.', 1)
                module = importlib.import_module(path_to_module)
                klass = getattr(module, class_name)
                worker = klass(cloud=cloud, lab=lab, **block)
                worker.set_is_debug(self._is_debug)
                workers_to_run.append(worker)
            except KeyError:
                raise ValueError('There is no "class" specifying the worker class path in {0}'.format(self._task_yaml_path))
            except ImportError:
                raise ValueError('{0} failed to import'.format(path_to_module))

        fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing

        if self._is_parallel:
            pool = multiprocessing.Pool(len(workers_to_run))
            results = pool.map(starter, workers_to_run)  # a list of {'name': 'monitor, scenario or disruptor name', 'success': True or False, 'n_exceptions': 10}
        else:
            results = map(starter, workers_to_run)

        exceptions = []
        for result in results:
            exceptions.extend(result.get('exceptions', []))

        tims_report = ''
        if self._is_report_to_tims:
            t = Tims()
            mercury_version, vts_version = lab.r_get_version()
            report_url = t.publish_result_to_tims(test_cfg_path=self._task_yaml_path, mercury_version=mercury_version, vts_version=vts_version, lab=lab, exceptions=exceptions, run_info=type_of_run)
            tims_report = 'and reported to {}'.format(report_url)
        self.log_to_slack(message=' {} finished with # exceptions={} {}'.format(type_of_run, len(exceptions), tims_report))

        return results
