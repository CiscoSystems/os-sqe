from lab.parallelworker import ParallelWorker
from lab.decorators import section


class EmptyMonitor(ParallelWorker):
    ARG_ARG1 = 'arg1'
    ARG_ARG2 = 'arg2'

    def check_arguments(self):
        assert self.arg1 > 0
        assert self.arg2 > 0

    @property
    def arg1(self):
        return self.args[self.ARG_ARG1]

    @property
    def arg2(self):
        return self.args[self.ARG_ARG2]

    @section('Setup EmptyMonitor')
    def setup_worker(self):
        pass

    def loop_worker(self):
        import time

        time.sleep(2)

    @section('Tearing down EmptyMonitor')
    def teardown_worker(self):
        pass
