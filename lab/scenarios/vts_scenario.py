from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class VtsScenario(TestCaseWorker):
    ARG_N_SERVERS = 'n_servers'
    ARG_N_NETWORKS = 'n_networks'
    ARG_UPTIME = 'uptime'
    ARG_RUN_INSIDE = 'run_inside'

    def check_arguments(self):
        assert self.n_networks >= 1
        assert self.n_servers >= 1
        assert self.uptime > 10

    @property
    def n_networks(self):
        return self.args[self.ARG_N_NETWORKS]

    @property
    def n_servers(self):
        return self.args[self.ARG_N_SERVERS]

    @property
    def uptime(self):
        return self.args[self.ARG_UPTIME]

    @property
    def run_inside(self):
        return self.args[self.ARG_RUN_INSIDE]

    @property
    def servers(self):
        return self.args['servers']

    @servers.setter
    def servers(self, servers):
        self.args['servers'] = servers

    @property
    def image(self):
        return self.args['image']

    @image.setter
    def image(self, image):
        self.args['image'] = image

    @property
    def flavor(self):
        return self.args['flavor']

    @flavor.setter
    def flavor(self, flavor):
        self.args['flavor'] = flavor

    @property
    def keypair(self):
        return self.args['keypair']

    @keypair.setter
    def keypair(self, key):
        self.args['keypair'] = key

    @property
    def _is_border_leaf_attached(self):
        return self.args.get('is-border-leaf-attached', False)

    @section('Setup')
    def setup_worker(self):
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_image import CloudImage
        from lab.cloud.cloud_key_pair import CloudKeyPair

        # self.pod.vtc.r_vtc_setup()
        self.cleanup()
        self.cloud.os_all()
        self.keypair = CloudKeyPair.create(cloud=self.cloud)
        self.image = CloudImage.create(cloud=self.cloud, image_name=CloudImage.SQE_PERF)
        self.flavor = CloudFlavor.create(cloud=self.cloud, flavor_type=CloudFlavor.TYPE_VTS)

    @section('Creating networks')
    def network_part(self):
        from lab.cloud.cloud_network import CloudNetwork

        nets = CloudNetwork.create(common_part_of_name='int', how_many=self.n_networks, cloud=self.cloud)
        self._wait_for_vtc_networks(nets=nets)
        return nets

    @section('Waiting till VTC registers networks')
    def _wait_for_vtc_networks(self, nets):
        import time

        for i in range(10):
            vts_nets, _ = self.pod.vtc.api_openstack()
            if {x.id for x in nets}.issubset({x.id for x in vts_nets}):
                break
            time.sleep(5)
        else:
            raise RuntimeError('{}: VTC failed to register networks'.format(self))

    @section('Ping servers')
    def ping_servers(self):
        n_packets = 50

        ans = self.servers[0].console_exe('ping -c {} {}'.format(n_packets, self.servers[1].ips[0]))
        if '{0} packets transmitted, {0} received, 0% packet loss'.format(n_packets) not in ans:
            raise RuntimeError(ans)
        return '50 packets send'

    @section('Iperf servers')
    def iperf_servers(self):
        server_passive = self.servers[0]
        server_same = [x for x in self.servers if x.get_compute_host() == server_passive.get_compute_host()][0]
        server_other = [x for x in self.servers if x.get_compute_host() != server_passive.get_compute_host()][0]

        server_passive.exe('iperf -s -p 1111 &')  # run iperf in listening mode on first server of first compute host
        a = [x.exe('{} -c {} -p 1111'.format(self.run_inside, server_passive.ip)) for x in [server_same, server_other]]
        return a

    @section('Running test')
    def loop_worker(self):
        import time
        from lab.cloud.cloud_server import CloudServer

        nets = self.network_part()
        self.servers = CloudServer.create(how_many=self.n_servers, flavor=self.flavor, image=self.image, on_nets=nets, key=self.keypair, timeout=self.timeout, cloud=self.cloud)

        self.log('Waiting 100 sec to settle servers...')
        time.sleep(100)
        start_time = time.time()

        while time.time() - start_time < self.uptime:
            if self.run_inside.startswith('iperf'):
                return self.iperf_servers()
            else:
                return self.ping_servers()
        self.delete_servers()

    @section('Deleting servers')
    def delete_servers(self):
        self.cloud.os_server_delete(servers=self.servers)

    def cleanup(self):
        # self.pod.vtc.r_vtc_del_border_leaf_ports()
        self.cloud.os_cleanup(is_all=True)

    @section(message='Assert no network in VTC')
    def check_vts_networks(self):
        vtc_networks = self.pod.vtc.r_vtc_show_openstack_network()
        if vtc_networks:
            raise RuntimeError('Networks are not deleted in VTC: {}'.format(vtc_networks))

    def detach_border_leaf(self):
        self.pod.vtc.r_vtc_delete_border_leaf_port()

    @section(message='Attach border leaf')
    def attach_border_leaf(self, nets):
        import time

        self.check_nve(is_attached=False)
        self.pod.vtc.r_vtc_create_border_leaf_port(nets)
        time.sleep(10)
        self.mgm.r_create_access_points(nets)
        self.check_nve(is_attached=True)

    def teardown_worker(self):
        self.cleanup()

    def check_nve(self, is_attached):
        comp_names = set([x.compute.id for x in self.servers])

        for n9 in self.pod.vim_tors:
            nve_ips = [x['peer-ip'] for x in n9.n9_show_nve_peers()]
            if is_attached:  # attaching border leaf should create additional peer to mgm node
                for comp_name in comp_names:
                    raise RuntimeError('{}: nve is not empty {} {} '.format(n9, nve_ips, comp_name))
            else:  # there should be nve peers connected to all computes where some instances run and no peer for mgm
                continue
