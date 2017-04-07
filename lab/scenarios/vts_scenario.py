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

    @section('Create servers')
    def create_servers(self, on_nets):
        from lab.cloud import CloudServer

        self._kwargs['servers'] = CloudServer.create(how_many=self._n_servers, flavor_name='sqe-vts', image=self._image, on_nets=on_nets, timeout=self._timeout, cloud=self.get_cloud())

    @section('Ping servers')
    def ping_servers(self):
        for server in self._kwargs['servers']:
            n_packets = 50
            for ip in server.get_ssh_ip():
                ans = self.get_mgmt().exe('ping -c {} {}'.format(n_packets, ip), is_warn_only=True)
                if '{0} packets transmitted, {0} received, 0% packet loss'.format(n_packets) not in ans:
                    raise RuntimeError(ans)

    @section('Iperf servers')
    def iperf_servers(self):
        server_passive = self._kwargs['servers'][0]
        server_same = [x for x in self._kwargs['servers'] if x.get_compute_host() == server_passive.get_compute_host()][0]
        server_other = [x for x in self._kwargs['servers'] if x.get_compute_host() != server_passive.get_compute_host()][0]

        ip = server_passive.get_ssh_ip()
        server_passive.exe('iperf -s -p 1111 &')  # run iperf in listening mode on first server of first compute host
        return [x.exe('{} -c {} -p 1111'.format(self._runner, ip)) for x in [server_same, server_other]]

    @section('Running test')
    def loop_worker(self):
        import time

        nets = self._network_part()

        self.create_servers(on_nets=nets)
        self.attach_border_leaf(nets=nets)

        time.sleep(30)
        start_time = time.time()

        while time.time() - start_time < self._uptime:
            if self._runner.startswith('iperf'):
                return self.iperf_servers()
            else:
                self.ping_servers()
        self.delete_servers()

    @section('Deleting servers')
    def delete_servers(self):
        if 'servers' in self._kwargs:
            self.get_cloud().os_server_delete(servers=self._kwargs['servers'])

    @section('Cleaning all objects observed in cloud')
    def cleanup(self):
        self.delete_servers()
        self.detach_border_leaf()
        self.get_cloud().os_cleanup(is_all=True)
        self.check_vts_networks()

    @section(message='Assert no network in VTC')
    def check_vts_networks(self):
        vtc_networks = self._vtc.r_vtc_show_openstack_network()
        if vtc_networks:
            raise RuntimeError('Networks are not deleted in VTC: {}'.format(vtc_networks))

    @section(message='Detach border leaf')
    def detach_border_leaf(self):
        self._vtc.r_vtc_delete_border_leaf_port()

    @section(message='Attach border leaf', estimated_time=10)
    def attach_border_leaf(self, nets):
        self._vtc.r_vtc_create_border_leaf_port(nets)
        self.get_mgmt().r_create_access_points(nets)

    def teardown_worker(self):
        self.cleanup()
