from lab.test_case_worker import TestCaseWorker


class CloudDisruptor(TestCaseWorker):
    ARG_NODE_TO_DISRUPT = 'node_to_disrupt'
    ARG_METHOD_TO_DISRUPT = 'method_to_disrupt'

    def check_arguments(self):
        assert self.node_to_disrupt in ['control', 'compute'], '{}: unknown node_to_disrupt "{}"'.format(self, self.node_to_disrupt)
        assert self.method_to_disrupt in ['reboot'], '{}: unknown method_to_disrupt "{}"'.format(self, self.method_to_disrupt)

    @property
    def node_to_disrupt(self):
        return self.args[self.ARG_NODE_TO_DISRUPT]

    @property
    def method_to_disrupt(self):
        return self.args[self.ARG_METHOD_TO_DISRUPT]

    def setup_worker(self):
        pass

    def loop_worker(self):
        self.cloud.os_disrupt(node=self.node_to_disrupt, method=self.method_to_disrupt)
