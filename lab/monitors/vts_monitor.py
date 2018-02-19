from lab.test_case_worker import TestCaseWorker


class VtsMonitor(TestCaseWorker):

    def check_arguments(self):
        pass

    def setup_worker(self):
        pass

    def loop_worker(self):
        nets, srvs = self.pod.vtc.api_openstack()
        self.pod.vtc.r_vtc_crm_mon('monitor'),
        self.log('n_nets={}'.format(len(nets)))
