from lab.test_case_worker import TestCaseWorker


class DeleteScenario(TestCaseWorker):
    ARG_MANDATORY_DELETE = 'delete'

    @property
    def delete(self):
        return self.args[self.ARG_MANDATORY_DELETE]

    def check_arguments(self):
        assert self.run == 1
        assert self.delete in ['all', 'sqe']

    def setup_worker(self):
        self.log(self.cloud.STATUS_OS_CLEANING)
        self.cloud.os_cleanup(is_all=self.delete == 'all')
        self.log(self.cloud.STATUS_OS_CLEANED)

    def loop_worker(self):
        pass
