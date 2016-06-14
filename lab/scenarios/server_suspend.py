from lab.worker import Worker


class ServerSuspend(Worker):
    # noinspection PyAttributeOutsideInit
    def setup(self):
        self.name = self._kwargs.get('name', '')

    def loop(self):
        servers = self._cloud.server_list()
        for server in servers:
            server_name = server['Name']
            if self.name in server_name:
                self._cloud.server_suspend(server_name)
