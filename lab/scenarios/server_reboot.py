from lab.worker import Worker


class ServerReboot(Worker):
    # noinspection PyAttributeOutsideInit
    def setup(self):
        self.name = self._kwargs.get('name', '')
        self.hard = self._kwargs.get('hard', 'False').lower() == 'true'

    def loop(self):
        servers = self._cloud.server_list()
        for server in servers:
            server_name = server['Name']
            if self.name in server_name:
                self._cloud.server_reboot(server_name, hard=self.hard)
