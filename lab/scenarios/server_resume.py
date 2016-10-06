from lab.parallelworker import ParallelWorker


class ServerResume(ParallelWorker):
    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        self.name = self._kwargs.get('name', '')

    def loop_worker(self):
        servers = self._cloud.server_list()
        for server in servers:
            server_name = server['Name']
            if self.name in server_name:
                self._cloud.server_resume(server_name)
