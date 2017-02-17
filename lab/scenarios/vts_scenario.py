from lab.parallelworker import ParallelWorker
from lab.decorators import section


class VtsScenario(ParallelWorker):
    def check_arguments(self, **kwargs):
        try:
            self.log('n. of nets={} n. servers={} uptime={} run={}'.format(self._n_nets, self._n_servers, self._uptime, self._runner))
        except KeyError as ex:
            raise ValueError('{}: no required parameter "{}"'.format(self, ex))

        if len(self.get_cloud().get_computes()) < 2:
            raise RuntimeError('{}: not possible to run on this cloud, number of compute hosts less then 2'.format(self))

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
        return self._lab.get_vtc()[0]

    @section('Setup')
    def setup_worker(self):
        self.get_cloud().os_cleanup()
        self.get_cloud().os_keypair_create()
        self.get_cloud().os_image_create('iperf')
        self.get_cloud().os_flavor_create('vts')

    @section('Creating networks')
    def _network_part(self):
        from lab.cloud import CloudNetwork

        nets = CloudNetwork.create(common_part_of_name='internal', class_a=1, how_many=self._n_nets, is_dhcp=False, cloud=self.get_cloud())
        self._wait_for_vtc_networks(nets=nets)

    @section('Waiting till VTC registers networks')
    def _wait_for_vtc_networks(self, nets):
        import time

        required = [(x.get_net_id(), x.get_segmentation_id()) for x in nets]
        max_retries = 10
        while True:
            vtc_nets = self._vtc.r_vtc_show_openstack_network()
            actual = [(x['id'], x['provider-segmentation-id']) for x in vtc_nets]
            if set(required).issubset(set(actual)):
                return
            if max_retries == 0:
                self.log(''.format(required, actual))
                raise RuntimeError('{}: VTC failed to register networks required={} actual={}'.format(self, required, actual))
            time.sleep(5)
            max_retries -= 1

    @section('Creating instances')
    def _instances_part(self, on_nets, timeout):
        from lab.cloud import CloudServer

        return CloudServer.create(how_many=self._n_servers, flavor_name='vts', image='iperf', on_nets=on_nets, timeout=timeout, cloud=self.get_cloud())

    @section('Pinging instances')
    def _ping_part(self, servers):
        for server in servers:
            n_packets = 50
            ans = self._build_node.exe('ping -c {} {}'.format(n_packets, server.get_ssh_ip()), is_warn_only=True)
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

        start_time = time.time()

        nets = self._network_part()
        self._vtc.r_vtc_set_port_for_border_leaf()
        self._build_node.r_create_access_points(nets)

        servers = self._instances_part(on_nets=nets)

        while time.time() - start_time < self._uptime:
            if self._runner.startswith('iperf'):
                return self._iperf_part(servers)
            else:
                self._ping_part(servers)

        start_delete_time = time.time()
        [s.delete() for s in servers]
        self.log('Instances deleted in {} sec'.format(time.time() - start_delete_time))

        self._cloud.os_cleanup()

    @staticmethod
    def debug_output():
        return '''WARNING: attempt to set TCP maximum segment size to 9000, but got 536
------------------------------------------------------------
Client connecting to 10.0.5.11, TCP port 1111
TCP window size: 85.0 KByte (default)
------------------------------------------------------------
[  3] local 10.0.5.12 port 52724 connected with 10.0.5.11 port 1111
[ ID] Interval       Transfer     Bandwidth
[  3]  0.0-10.7 sec  10.0 GBytes  8.03 Gbits/sec
'''