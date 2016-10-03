from lab.worker import Worker


class ServerRebuild(Worker):
    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        self.name = self._kwargs.get('name', '')
        self.image = self._kwargs['image']

    def loop_worker(self):
        servers = self._cloud.server_list()
        for server in servers:
            server_name = server['Name']
            if self.name in server_name:
                self._cloud.server_rebuild(server_name, image=self.image)
