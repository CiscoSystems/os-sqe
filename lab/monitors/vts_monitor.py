from lab.test_case_worker import TestCaseWorker


class VtsMonitor(TestCaseWorker):

    def check_arguments(self):
        pass

    def setup_worker(self):
        pass

    def loop_worker(self):
        self.log('cluster={}'.format(self.pod.vtc.api_vtc_ha()))
        self.log('openstack={}'.format(self.pod.vtc.api_openstack()))

