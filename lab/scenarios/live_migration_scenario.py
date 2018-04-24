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
        server = self.cloud.servers[0]

        res = ' '.join(server.migrate(self.migration))
        self.passed(message=res) if 'migrated' in res else self.failed(message=res, is_stop_running=True)
