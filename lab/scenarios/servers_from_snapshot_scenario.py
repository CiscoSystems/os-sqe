from lab.test_case_worker import TestCaseWorker


class ServersFromSnapshotScenario(TestCaseWorker):
    ARG_MANDATORY_N_SERVERS = 'n_servers'
    ARG_MANDATORY_UPTIME = 'uptime'

    def check_arguments(self):
        assert self.n_servers >= 1
        assert self.uptime > 10

    @property
    def n_servers(self):
        return self.args[self.ARG_MANDATORY_N_SERVERS]

    @property
    def uptime(self):
        return self.args[self.ARG_MANDATORY_UPTIME]

    def setup_worker(self):
        pass

    def loop_worker(self):
        import time
        from lab.cloud.cloud_server import CloudServer

        self.log(self.STATUS_SERVER_CREATING + ' n=' + str(self.n_servers))
        self.cloud.os_all()
        flavor = self.cloud.flavors[0]
        image = self.cloud.images[0]
        keypair = self.cloud.keypairs[0]

        self.servers = CloudServer.create(how_many=self.n_servers, flavor=flavor.name, image=image.name, on_nets=[], key=keypair.name, timeout=self.timeout, cloud=self.cloud)
        self.log('Waiting 30 sec to settle servers...')
        time.sleep(30)
        self.log(self.STATUS_SERVER_CREATED)
        if str(self.uptime) != 'forever':
            time.sleep(self.uptime)
