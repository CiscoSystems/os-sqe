from lab.parallelworker import ParallelWorker
from lab.decorators import section


class VtsScenario(ParallelWorker):

    def check_config(self):
        return 'n. of nets={} n. servers={} uptime={} run={}'.format(self._n_nets, self._n_servers, self._uptime, self._runner)

    @property
    def _n_nets(self):
        return self._kwargs['how-many-networks']

    @property
    def _n_servers(self):
        return self._kwargs['how-many-servers']

    @property
    def _uptime(self):
        return self._kwargs['uptime']

    @property
    def _runner(self):
        return self._kwargs['what-to-run-inside']

    @property
    def _vtc(self):
        return self.get_lab().get_vtc()[0]

    @property
    def _image(self):
        return self._kwargs['image']

    @section('Setup')
    def setup_worker(self):
        self.cleanup()
        self.get_cloud().os_keypair_create()
        self._kwargs['image'] = self.get_cloud().os_image_create('sqe-iperf')
        self.get_cloud().os_flavor_create('vts')

    @section('Creating networks')
    def _network_part(self):
        from lab.cloud import CloudNetwork

        nets = CloudNetwork.create(common_part_of_name='internal', class_a=1, how_many=self._n_nets, is_dhcp=False, cloud=self.get_cloud())
        self._wait_for_vtc_networks(nets=nets)
        return nets

    @section('Waiting till VTC registers networks')
    def _wait_for_vtc_networks(self, nets):
        import time

        required = [(x.get_net_id(), str(x.get_segmentation_id())) for x in nets]
        max_retries = 10
        while True:
            vtc_nets = self._vtc.r_vtc_show_openstack_network()
            actual = [(x['id'], x['provider-segmentation-id']) for x in vtc_nets]
            if set(required) <= (set(actual)):
                return
            if max_retries == 0:
                self.log(''.format(required, actual))
                raise RuntimeError('{}: VTC failed to register networks required={} actual={}'.format(self, required, actual))
            time.sleep(5)
            max_retries -= 1

    @section('Creating instances')
    def _instances_part(self, on_nets):
        from lab.cloud import CloudServer

        return CloudServer.create(how_many=self._n_servers, flavor_name='sqe-vts', image=self._image, on_nets=on_nets, timeout=self._timeout, cloud=self.get_cloud())

    @section('Pinging instances')
    def _ping_part(self, servers):
        for server in servers:
            n_packets = 50
            ans = self.get_mgmt().exe('ping -c {} {}'.format(n_packets, server.get_ssh_ip()), is_warn_only=True)
            if '{0} packets transmitted, {0} received, 0% packet loss'.format(n_packets) not in ans:
                raise RuntimeError(ans)

    @section('Running iperf')
    def _iperf_part(self, servers):
        server_passive = servers[0]
        server_same = [x for x in servers if x.get_compute_host() == server_passive.get_compute_host()][0]
        server_other = [x for x in servers if x.get_compute_host() != server_passive.get_compute_host()][0]

        ip = server_passive.get_ssh_ip()
        server_passive.exe('iperf -s -p 1111 &')  # run iperf in listening mode on first server of first compute host
        return [x.exe('{} -c {} -p 1111'.format(self._runner, ip)) for x in [server_same, server_other]]

    @section('Running test')
    def loop_worker(self):
        import time

        nets = self._network_part()

        self.set_border_leaf(nets=nets)
        servers = self._instances_part(on_nets=nets)

        start_time = time.time()

        while time.time() - start_time < self._uptime:
            if self._runner.startswith('iperf'):
                return self._iperf_part(servers)
            else:
                self._ping_part(servers)
        self._delete_servers()

    @section('Deleting servers')
    def _delete_servers(self, servers):
        self.get_cloud().os_server_delete(servers=servers)

    @section('Cleaning all objects observed in cloud')
    def cleanup(self):
        self._vtc.r_vtc_delete_border_leaf_port()
        self.get_cloud().os_cleanup(is_all=True)
        vtc_networks = self._vtc.r_vtc_show_openstack_network()
        if vtc_networks:
            raise RuntimeError('Networks are not deleted in VTC: {}'.format(vtc_networks))

    def teardown_worker(self):
        self.cleanup()

    @section(message='Setting border leaf', estimated_time=10)
    def set_border_leaf(self, nets):
        self._vtc.r_vtc_create_border_leaf_port(nets)
        self.get_mgmt().r_create_access_points(nets)
