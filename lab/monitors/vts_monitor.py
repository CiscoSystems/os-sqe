from lab.test_case_worker import TestCaseWorker


class VtsMonitor(TestCaseWorker):

    def check_arguments(self):
        pass

    def setup_worker(self):
        pass

    def loop_worker(self):
        self.log('cluster={}'.format(self.pod.vtc.r_vtc_show_ha_cluster_members()))
        self.log('networks={}'.format(self.pod.vtc.r_vtc_show_openstack_network()))
        self.log('subnetworks={}'.format(self.pod.vtc.r_vtc_show_openstack_subnet()))
        self.log('ports={}'.format(self.pod.vtc.r_vtc_show_openstack_port()))
