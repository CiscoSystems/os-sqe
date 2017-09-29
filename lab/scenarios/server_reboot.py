from lab.test_case_worker import TestCaseWorker


class ServerReboot(TestCaseWorker):
    def check_arguments(self, **kwargs):
        pass

    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        self.name = self._kwargs.get('name', '')
        self.hard = self._kwargs.get('hard', 'False').lower() == 'true'

    def loop_worker(self):
        servers = self._cloud.os_server_list()
        for server in servers:
            server_name = server['Name']
            if self.name in server_name:
                self._cloud.os_server_reboot(server_name, hard=self.hard)
