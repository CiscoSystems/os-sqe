from lab.test_case_worker import TestCaseWorker


class DeleteScenario(TestCaseWorker):
    ARG_MANDATORY_DELETE = 'delete'

    @property
    def delete(self):
        return self.args[self.ARG_MANDATORY_DELETE]

    def check_arguments(self):
        assert self.run == 1
        assert self.delete in ['all', 'own']

    def setup_worker(self):
        pass

    def loop_worker(self):
        self.log(self.STATUS_OS_CLEANING)
        self.cloud.os_cleanup(is_all=self.delete == 'all')
        self.log(self.STATUS_OS_CLEANED)
