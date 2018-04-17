from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn
from lab.laboratory import Laboratory


class FakeCloud(object):
    pod = Laboratory()


def starter(worker):
    return worker.start_worker_parallel()


class RunnerHA(WithConfig, WithLogMixIn):
    def __init__(self):
        from prettytable import PrettyTable

        self.status_tbl = PrettyTable()
        self.status_tbl.field_names = ['name', 'status', 'time, sec']
        self.err_tbl = PrettyTable()
        self.err_tbl.field_names = ['name', 'text']
        self.cloud = None

    def __repr__(self):
        return u''

    def execute_single_test(self, test_case):
        import multiprocessing
        import fabric.network
        import time

        self.log('\n\n')
        test_case.log('status=start')
        test_case.time = time.time()  # used to calculate duration of test
        test_case.cloud = self.cloud
        manager = multiprocessing.Manager()
        status_dict = manager.dict()

        workers = test_case.workers
        for worker in workers:
            worker.cloud = self.cloud
            worker.status_dict = status_dict
            worker.set_status(worker.STATUS_CREATED)
            if not test_case.is_debug:
                try:
                    worker.setup_worker()  # run all setup_worker in non-parallel
                except RuntimeError:    # just collect all exception messages in TCWs
                    pass
            else:
                worker.log('Setup...')
        if not test_case.is_failed:
            time.sleep(2)
            fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing
            time.sleep(2)

            pool = multiprocessing.Pool(len(workers))
            test_case.log('******* PARALLEL EXECUTION STARTS *******')
            pool.map(starter, workers)
            test_case.log('******* PARALLEL EXECUTION FINISH *******')

        test_case.after_run(status_tbl=self.status_tbl, err_tbl=self.err_tbl)

        self.log(self.status_tbl.get_string())
        self.log(self.err_tbl.get_string())

        if not test_case.is_debug:
            map(lambda x: x.teardown_worker(), workers)  # run all teardown_workers
        fabric.network.disconnect_all()
        test_case.log('status=finish')

    def run(self, pod_name, test_regex, is_noclean, is_debug):
        available_tc = self.ls_configs(directory='ha')
        test_paths = sorted(filter(lambda x: test_regex in x, available_tc))

        if not test_paths:
            raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

        self.log('Running n_tests={}'.format(len(test_paths)))
        tests = self.create_tests(test_paths=test_paths, is_noclean=is_noclean, is_debug=is_debug)

        possible_drivers = set(reduce(lambda l,x: x.possible_drivers + l, tests, []))
        if len(test_paths) == 1 and test_paths[0] == 'dev01-test-parallel.yaml':  # special test case to test infrastructure itself, does not require cloud
            self.cloud = FakeCloud()
        else:
            self.cloud = self.init_cloud(pod_name=pod_name, possible_drivers=possible_drivers)

        # start_time = time.time()
        map(lambda x: self.execute_single_test(test_case=x), tests)

        # if type(self.cloud) is not FakeCloud:
        #     elk = Elk(proxy=self.cloud.mediator)
        #     elk.filter_error_warning_in_last_seconds(seconds=time.time() - start_time)
        #     self.cloud.pod.r_collect_info(regex='error', comment=test_regex)

    @staticmethod
    def init_cloud(pod_name, possible_drivers):
        from lab.deployers.deployer_existing_cloud import DeployerExistingCloud

        deployer = DeployerExistingCloud(lab_name=pod_name, allowed_drivers=possible_drivers)
        cloud = deployer.execute({'clouds': [], 'servers': []})
        return cloud

    def create_tests(self, test_paths, is_noclean, is_debug):
        from lab.test_case import TestCase

        unique_id_seen = []
        test_cases = []
        for test_path in test_paths:
            test = TestCase(path=test_path, is_noclean=is_noclean, is_debug=is_debug, cloud=self.cloud)
            assert test.unique_id not in unique_id_seen
            unique_id_seen.append(test.unique_id)
            test_cases.append(test)

        return test_cases
