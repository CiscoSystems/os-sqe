from lab.test_case_worker import TestCaseWorker


class NetworksScenario(TestCaseWorker):
    ARG_MANDATORY_N_NETWORKS = 'n_networks'
    ARG_MANDATORY_UPTIME = 'uptime'

    STATUS_NETWORK_CREATING = 'status=NetworkCreating'
    STATUS_NETWORK_CREATED = 'status=NetworkCreated'
    STATUS_NETWORK_DELETED = 'status=NetworkDeleted'

    def check_arguments(self):
        assert self.n_networks >= 1
        assert self.uptime > 10

    @property
    def n_networks(self):
        return self.args[self.ARG_MANDATORY_N_NETWORKS]

    @property
    def uptime(self):
        return self.args[self.ARG_MANDATORY_UPTIME]

    @property
    def nets(self):
        return self.args['nets']

    @nets.setter
    def nets(self, nets):
        self.args['servers'] = nets

    def setup_worker(self):
        pass

    def loop_worker(self):
        from lab.cloud.cloud_network import CloudNetwork
        from lab.cloud.cloud_router import CloudRouter

        self.log('status=creating {} network{{s}}'.format(self.n_networks))
        self.nets = CloudNetwork.create(common_part_of_name='', how_many=self.n_networks, class_a=10, cloud=self.cloud)
        self.passed(self.STATUS_NETWORK_CREATED)
        exts = [x for x in self.cloud.networks if x.is_external]
        if exts:
            self.log(CloudRouter.STATUS_ROUTER_CREATING)
            CloudRouter.create(cloud=self.cloud)
            self.passed(CloudRouter.STATUS_ROUTER_CREATED)
