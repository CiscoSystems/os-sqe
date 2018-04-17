from lab.test_case_worker import TestCaseWorker


class SnapshotScenario(TestCaseWorker):
    def setup_worker(self):
        pass

    def loop_worker(self):
        self.log(self.STATUS_SERVER_SNAPSHOTING)
        self.cloud.os_all()
        self.cloud.servers[0].snapshot()
        self.log(self.STATUS_SERVER_SNAPSHOTED)
