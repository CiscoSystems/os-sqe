from lab.test_case_worker import TestCaseWorker


class VtsMonitor(TestCaseWorker):

    def check_arguments(self):
        pass

    def setup_worker(self):
        pass

    def loop_worker(self):
        nets, srvs = self.pod.vtc.api_openstack()
        ha = self.pod.vtc.r_vtc_crm_mon()

        self.log('n_nets={} master={} slave={} online={} offline={} when=in_monitor'.format(len(nets), ha['master'], ha['slave'], ha['online'], ha['offline']))
