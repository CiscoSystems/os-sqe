from lab.with_config import WithConfig


def starter(worker):
    return worker.start_worker_parallel()


class RunnerHA(WithConfig):
    @staticmethod
    def execute_single_test(workers, cloud, tims):
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
        results = pool.map(starter, workers)
        tims.publish_result(test_cfg_path=workers[0].test_cfg_path, results=results)

        try:
            map(lambda x: x.teardown_worker(), workers)  # run all teardown_workers
        except Exception as ex:
            with cloud.pod.open_artifact('exception-in-teardown.txt'.format(), 'w') as f:
                f.write(str(ex))

    @staticmethod
    def run(lab_name, test_regex, is_noclean):
        import time
        from lab.deployers.deployer_existing import DeployerExisting
        from lab.tims import Tims
        from lab.elk import Elk

        tests = RunnerHA.check_configs(test_regex=test_regex, is_noclean=is_noclean)

        deployer = DeployerExisting(lab_name=lab_name)
        cloud = deployer.execute({'clouds': [], 'servers': []})
        if len(cloud.computes) < 2:
            raise RuntimeError('{}: not possible to run on this cloud, number of compute hosts less then 2'.format(cloud))

        tims = Tims(pod=cloud.pod)

        start_time = time.time()
        map(lambda x: RunnerHA.execute_single_test(workers=x, cloud=cloud, tims=tims), tests)

        elk = Elk(proxy=cloud.mediator)
        elk.filter_error_warning_in_last_seconds(seconds=time.time() - start_time)

        cloud.pod.r_collect_info(regex='error', comment=test_regex)

    @staticmethod
    def check_configs(test_regex, is_noclean):
        available_tc = RunnerHA.ls_configs(directory='ha')
        test_cfg_paths = sorted(filter(lambda x: test_regex in x, available_tc))

        if not test_cfg_paths:
            raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

        return [RunnerHA.check_single_test(test_cfg_path=x, is_noclean=is_noclean) for x in test_cfg_paths]

    @staticmethod
    def check_single_test(test_cfg_path, is_noclean):
        import importlib

        worker_names_already_seen =[]

        workers = []
        status_dict = {}
        for worker_args in RunnerHA.read_config_from_file(config_path=test_cfg_path, directory='ha'):
            if 'class' not in worker_args:
                continue
            if 'name' not in worker_args:
                raise ValueError('{} in {} should define "name"'.format(worker_args['class'], test_cfg_path))
            if worker_args['name'] in worker_names_already_seen:
                raise ValueError('{} in {} defines name "{}" which is already defined somewhere else'.format(worker_args['class'], test_cfg_path, worker_args['name']))

            path_to_module, class_name = worker_args['class'].rsplit('.', 1)
            try:
                mod = importlib.import_module(path_to_module)
            except ImportError:
                raise ValueError('{}: tries to run {}.py which does not exist'.format(test_cfg_path, path_to_module))
            try:
               klass = getattr(mod, class_name)
            except AttributeError:
                raise ValueError('Please create class {} in {}.py'.format(class_name, path_to_module))
            worker_args['test_cfg_path'] = test_cfg_path
            worker_args['is_noclean'] = is_noclean
            worker = klass(args_dict=worker_args)
            worker.status_dict = status_dict
            workers.append(worker)

        for worker in workers:
            for attr_name in ['run_while', 'run_after']:
                attr = getattr(worker, attr_name)
                if type(attr) is not list:
                    setattr(worker, attr_name, [attr])
                not_in_status = filter(lambda x: x not in worker.status_dict.keys(), getattr(worker, attr_name))
                if not_in_status:
                    worker.raise_exception(ValueError, 'run_while has "{}" which is invalid. Valid are {}'.format(not_in_status, worker.status_dict.keys()))

            if worker.run_while:
                if any([worker.run_after, worker.n_repeats]):
                    worker.raise_exception(ValueError, 'run_while can not co-exists with either of n_repeats and run_after')
            elif worker.n_repeats < 1:
                    worker.raise_exception(ValueError, 'please define either wun_while or n_repeats >= 1')

            try:
                worker.check_config()
            except KeyError as ex:
                worker.raise_exception(ValueError, 'no required parameter "{}"'.format(ex))
        return workers
