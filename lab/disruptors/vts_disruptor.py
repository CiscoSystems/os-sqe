from lab.test_case_worker import TestCaseWorker


class VtsDisruptor(TestCaseWorker):
    ARG_METHOD_TO_DISRUPT = 'method_to_disrupt'
    ARG_NODE_TO_DISRUPT = 'node_to_disrupt'
    ARG_DISRUPT_TIME = 'disrupt_time'

    @property
    def disrupt_time(self):
        return self.args[self.ARG_DISRUPT_TIME]

    @property
    def node_to_disrupt(self):
        return self.args[self.ARG_NODE_TO_DISRUPT]

    @property
    def method_to_disrupt(self):
        return self.args[self.ARG_METHOD_TO_DISRUPT]

    def check_arguments(self):
        possible_nodes = ['master-vtc', 'slave-vtc', 'master-vtsr', 'slave-vtsr']
        possible_methods = ['isolate-from-mx', 'isolate-from-api', 'isolate-from-t', 'vm-shutdown', 'vm-reboot', 'corosync-stop', 'ncs-stop']

        assert self.disrupt_time > 0
        assert self.node_to_disrupt in possible_nodes, '{} not in {}, check {}'.format(self.node_to_disrupt, possible_nodes, self.test_case.path)
        assert self.method_to_disrupt in possible_methods

    def setup_worker(self):
        if len(self.pod.vts) < 2:
            raise RuntimeError('This pod has no actual HA, single host runs all VTC virtuals: {}'.format(self.pod.vts[0].virtual_servers))

    def loop_worker(self):
        self.pod.vtc.disrupt(node_to_disrupt=self.node_to_disrupt, method_to_disrupt=self.method_to_disrupt, downtime=self.disrupt_time)  # chekc inside that node is back after disruption

