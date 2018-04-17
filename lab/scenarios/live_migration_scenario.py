from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class LiveMigrationScenario(TestCaseWorker):
    ARG_MANDATORY_HOW = 'migration'

    @property
    def migration(self):
        return self.args[self.ARG_MANDATORY_HOW]

    def check_arguments(self):
        assert self.migration in ['cold', 'live']

    def setup_worker(self):
        pass

    def loop_worker(self):
        self.cloud.os_all()
        server = self.cloud.servers[0]

        server.migrate(self.migration)
