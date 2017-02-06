from lab.parallelworker import ParallelWorker


class ServerRebuild(ParallelWorker):
    def check_arguments(self, **kwargs):
        pass

    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        self.name = self._kwargs.get('name', '')
        self.image = self._kwargs['image']

    def loop_worker(self):
        servers = self._cloud.os_server_list()
        for server in servers:
            server_name = server['Name']
            if self.name in server_name:
                self._cloud.os_server_rebuild(server_name, image=self.image)
