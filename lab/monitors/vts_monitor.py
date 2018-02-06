from lab.test_case_worker import TestCaseWorker


class VtsMonitor(TestCaseWorker):

    def check_arguments(self):
        pass

    def setup_worker(self):
        pass

    def loop_worker(self):
        ha = self.pod.vtc.api_vtc_ha()
        master_name = [x['hostname'] for x in ha['vtc-ha:vtc-ha']['nodes']['node'] if x['original-state'] == 'Master'][0]
        nets, srvs = self.pod.vtc.api_openstack()
        self.log('master={} n_nets={}'.format(master_name, len(nets)))
