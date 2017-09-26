from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


def starter(worker):
    return worker.start_worker_parallel()


class RunnerHA(WithConfig, WithLogMixIn):
    def execute_single_test(self, workers, cloud, tims):
        import multiprocessing
        import fabric.network
        import time

        manager = multiprocessing.Manager()
        status_dict = manager.dict()

        for worker in workers:
            worker.cloud = cloud
            worker.status_dict = status_dict
            worker.setup_worker()  # run all setup_worker in non-parallel
            worker.set_status(status=worker.STATUS_INITIALIZED)

        fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing
        time.sleep(2)

        pool = multiprocessing.Pool(len(workers))
        self.log('\n\n***AFTER THIS LINE PARALLEL EXECUTION STARTS***\n\n')
        results = pool.map(starter, workers)
        self.log('\n\n***PARALLEL EXECUTION FINISHED***\n\n')

        tims.publish_result(test_cfg_path=workers[0].test_cfg_path, results=results)

        try:
            map(lambda x: x.teardown_worker(), workers)  # run all teardown_workers
        except Exception as ex:
            with WithConfig.open_artifact('exception-in-teardown.txt'.format(), 'w') as f:
                f.write(str(ex))

    @staticmethod
    def run(lab_name, test_regex, is_noclean, is_debug):
        import time
        from lab.tims import Tims
        from lab.elk import Elk

        tests = RunnerHA.create_tests(test_regex=test_regex, is_noclean=is_noclean)
        if is_debug:
            return

        if 'dev-test-parallel' not in test_regex:
            cloud = RunnerHA.init_cloud(pod_name=lab_name)
            pod = cloud.pod
        else:
            cloud = None
            pod = None
        tims = Tims.create(pod=pod)

        runner = RunnerHA()
        start_time = time.time()
        map(lambda x: runner.execute_single_test(workers=x, cloud=cloud, tims=tims), tests)

        if cloud:
            elk = Elk(proxy=cloud.mediator)
            elk.filter_error_warning_in_last_seconds(seconds=time.time() - start_time)
            cloud.pod.r_collect_info(regex='error', comment=test_regex)

    @staticmethod
    def init_cloud(pod_name):
        from lab.deployers.deployer_existing import DeployerExisting

        deployer = DeployerExisting(lab_name=pod_name)
        cloud = deployer.execute({'clouds': [], 'servers': []})
        if len(cloud.computes) < 2:
            raise RuntimeError('{}: not possible to run on this cloud, number of compute hosts less then 2'.format(cloud))
        return cloud


    @staticmethod
    def create_tests(test_regex, is_noclean):
        available_tc = RunnerHA.ls_configs(directory='ha')
        test_cfg_paths = sorted(filter(lambda x: test_regex in x, available_tc))

        if not test_cfg_paths:
            raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

        return [RunnerHA.create_test_workers(test_cfg_path=x, is_noclean=is_noclean) for x in test_cfg_paths]

    @staticmethod
    def create_test_workers(test_cfg_path, is_noclean):
        import importlib

        worker_names_already_seen =[]

        headers_seen = []
        workers = []
        for worker_dic in RunnerHA.read_config_from_file(config_path=test_cfg_path, directory='ha'):  # list of dicts
            if 'class' not in worker_dic:
                headers_seen.extend(worker_dic.keys())
                if 'Folder' in worker_dic:
                    assert worker_dic['Folder'] in WithConfig.KNOWN_LABS['tims']['folders']
                continue
            if 'name' not in worker_dic:
                raise ValueError('{} in {} should define unique "name"'.format(worker_dic['class'], test_cfg_path))
            klass = worker_dic['class']
            path_to_module, class_name = klass.rsplit('.', 1)
            try:
                mod = importlib.import_module(path_to_module)
            except ImportError:
                raise ValueError('{}: tries to run {}.py which does not exist'.format(test_cfg_path, path_to_module))
            try:
               klass = getattr(mod, class_name)
            except AttributeError:
                raise ValueError('Please create class {} in {}.py'.format(class_name, path_to_module))
            worker_dic['test_cfg_path'] = test_cfg_path
            worker_dic['is_noclean'] = is_noclean
            worker = klass(args_dict=worker_dic)
            if worker.name in worker_names_already_seen:
                worker.raise_exception('uses name which is already seen in {}'.format(worker, test_cfg_path))
            else:
                worker_names_already_seen.append(worker.name)

            workers.append(worker)

        for worker in workers:
            for attr_name in [worker.ARG_RUN, worker.ARG_DELAY]:
                value = getattr(worker, attr_name)
                if type(value) is int:
                    continue
                wrong_names = filter(lambda x: x not in worker_names_already_seen, value)
                if wrong_names:
                    worker.raise_exception('has names "{}" which are invalid. Valid are {}'.format(wrong_names, worker_names_already_seen))
        required_headers_set = {'Title', 'Folder', 'Description'}
        assert set(headers_seen) == required_headers_set, '{}: no header(s) {}'.format(test_cfg_path, required_headers_set - set(headers_seen))

        return workers
