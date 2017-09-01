from lab.parallelworker import ParallelWorker
from lab.decorators import section


class VtsScenario(ParallelWorker):

    def check_config(self):
        return 'n. of nets={} n. servers={} uptime={} run={}'.format(self.n_nets, self.n_servers, self._uptime, self.run_cmd)

    @property
    def n_nets(self):
        return self._kwargs['how-many-networks']

    @property
    def n_servers(self):
        return self._kwargs['how-many-servers']

    @property
    def servers(self):
        return self._kwargs['servers']

    @servers.setter
    def servers(self, servers):
        self._kwargs['servers'] = servers

    @property
    def _uptime(self):
        return self._kwargs['uptime']

    @property
    def run_cmd(self):
        return self._kwargs['what-to-run-inside']

    @property
    def vtc(self):
        return self.pod.vtc[0]

    @property
    def image(self):
        return self._kwargs['image']

    @property
    def _is_border_leaf_attached(self):
        return self._kwargs.get('is-border-leaf-attached', False)

    @section('Setup')
    def setup_worker(self):
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_image import CloudImage

        self.cleanup()
        self.cloud.os_keypair_create()
        self._kwargs['image'] = CloudImage.create(cloud=self.cloud, image_name=CloudImage.SQE_PERF)
        self._kwargs['flavor'] = CloudFlavor.create(variant=CloudFlavor.TYPE_VTS)

    @section('Creating networks')
    def _network_part(self):
        from lab.cloud.cloud_network import CloudNetwork

        nets = CloudNetwork.create(common_part_of_name='int', how_many=self.n_nets, cloud=self.cloud)
        if self.pod.is_with_vts():
            self._wait_for_vtc_networks(nets=nets)
        return nets

    @section('Waiting till VTC registers networks')
    def _wait_for_vtc_networks(self, nets):
        import time

        required = [(x.net_id, str(x.segmentation_id)) for x in nets]
        for i in range(10):
            vtc_nets = self.vtc.r_vtc_show_openstack_network()
            actual = [(x['id'], x['provider-segmentation-id']) for x in vtc_nets]
            if set(required) <= (set(actual)):
                break
            time.sleep(5)
        else:
            raise RuntimeError('{}: VTC failed to register networks'.format(self))

    def create_servers(self, on_nets):
        from lab.cloud.cloud_server import CloudServer

        self._kwargs['servers'] = CloudServer.create(how_many=self.n_servers, flavor_name='sqe-vts', image=self.image, on_nets=on_nets, timeout=self._timeout, cloud=self.cloud)

    @section('Ping servers')
    def ping_servers(self):
        for server in self._kwargs['servers']:
            n_packets = 50
            for ip in server.get_ssh_ip():
                ans = self.mgmt.exe('ping -c {} {}'.format(n_packets, ip), is_warn_only=True)
                if '{0} packets transmitted, {0} received, 0% packet loss'.format(n_packets) not in ans:
                    raise RuntimeError(ans)

    @section('Iperf servers')
    def iperf_servers(self):
        server_passive = self._kwargs['servers'][0]
        server_same = [x for x in self._kwargs['servers'] if x.get_compute_host() == server_passive.get_compute_host()][0]
        server_other = [x for x in self._kwargs['servers'] if x.get_compute_host() != server_passive.get_compute_host()][0]

        ip = server_passive.get_ssh_ip()
        server_passive.exe('iperf -s -p 1111 &')  # run iperf in listening mode on first server of first compute host
        a = [x.exe('{} -c {} -p 1111'.format(self.run_cmd, ip)) for x in [server_same, server_other]]

        with self.pod.open_artifact('main-results-for-tims.txt'.format(), 'w') as f:
            f.write(a)

    @section('Running test')
    def loop_worker(self):
        import time

        nets = self._network_part()

        self.create_servers(on_nets=nets)
        if self.pod.is_with_vts():
            self.attach_border_leaf(nets=nets)

        start_time = time.time()

        while time.time() - start_time < self._uptime:
            if self.run_cmd.startswith('iperf'):
                return self.iperf_servers()
            else:
                self.ping_servers()
        self.delete_servers()

    @section('Deleting servers')
    def delete_servers(self):
        if 'servers' in self._kwargs:
            self.cloud.os_server_delete(servers=self._kwargs['servers'])

    @section('Cleaning all objects observed in cloud')
    def cleanup(self):
        if self.pod.vtc:
            self.detach_border_leaf()
        self.cloud.os_cleanup(is_all=True)
        if self.pod.vtc:
            self.check_vts_networks()

    @section(message='Assert no network in VTC')
    def check_vts_networks(self):
        vtc_networks = self.vtc.r_vtc_show_openstack_network()
        if vtc_networks:
            raise RuntimeError('Networks are not deleted in VTC: {}'.format(vtc_networks))

    @section(message='Detach border leaf')
    def detach_border_leaf(self):
        self.vtc.r_vtc_delete_border_leaf_port()

    @section(message='Attach border leaf')
    def attach_border_leaf(self, nets):
        import time

        self.check_nve()
        self.vtc.r_vtc_create_border_leaf_port(nets)
        time.sleep(10)
        self.mgm.r_create_access_points(nets)
        self.check_nve()

    def teardown_worker(self):
        self.cleanup()

    def check_nve(self, servers):
        comp_names = set([x.compute.id for x in servers])
        comp_t_ips = [self.pod.get_node_by_id(x).get for x in comp_names]

        for n9 in self.pod.get_tors():
            nve_ips = [x['peer-ip'] for x in n9.n9_show_nve_peers()]
            if self._is_border_leaf_attached: # attaching border leaf should create additional peer to mgm node
                for comp_name in comp_names:
                    raise RuntimeError('{}: nve is not empty {}'.format(n9, nve_ips))
            else:  # there should be nve peers connected to all computes where some instances run and no peer for mgm
                continue


