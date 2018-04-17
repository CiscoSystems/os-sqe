from lab.test_case_worker import TestCaseWorker


class NetworksScenario(TestCaseWorker):
    ARG_MANDATORY_N_NETWORKS = 'n_networks'
    ARG_MANDATORY_UPTIME = 'uptime'

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

    def create_networks(self):
        from lab.cloud.cloud_network import CloudNetwork

        self.log('status=creating {} network{{s}}'.format(self.n_networks))
        self.nets = CloudNetwork.create(common_part_of_name='', how_many=self.n_networks, class_a=10, cloud=self.cloud)

    def delete_networks(self):
        from lab.cloud.cloud_network import CloudNetwork

        CloudNetwork.delete(nets=self.nets, cloud=self.cloud)

    def loop_worker(self):
        import time

        self.create_networks()

        if str(self.uptime) != 'forever':
            time.sleep(self.uptime)
            self.delete_networks()
