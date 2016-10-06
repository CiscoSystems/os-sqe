from lab.worker import Worker


class VtsScenario(Worker):
    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        self._n_instances = self._kwargs['how-many-servers']
        self._n_nets = self._kwargs['how-many-networks']
        self._what_to_run_inside = self._kwargs.get('what-to-run-inside')  # if nothing specified - do not run anything in addition to ping
        self._build_node = self._lab.get_director()
        self._cloud.os_cleanup()
        self._image = self._cloud.os_image_create()
        self._cloud.os_keypair_create()

    def __repr__(self):
        return u'worker=VtsScenario'

    def loop_worker(self):
        from lab.nodes.lab_server import LabServer

        internal_nets = self._cloud.os_network_create(common_part_of_name='internal', class_a=10, how_many=self._n_nets, is_dhcp=False)

        servers_per_compute_node = {1: [], 2: []}
        all_servers = []
        for i in range(1, self._n_instances + 1):
            port_pids = self._cloud.os_port_create(server_name=str(i), on_nets=internal_nets, is_fixed_ip=True)
            self._log.info('instance={} status=requested'.format(i))
            server_info = self._cloud.os_server_create(name=str(i), flavor='m1.medium', image_name=self._image['name'], on_ports=port_pids)
            server = LabServer(node_id='vm{}'.format(i), role='OS-VM', lab='FAKE')
            server.set_proxy_server(self._build_node)

            all_servers.append(server)
            servers_per_compute_node[server_info['compute-node']].append(server)
            self._log.info('instance={} status=created'.format(i))

        for server in all_servers:
            server.exe('ping -c5 {}'.format(servers_per_compute_node[1][0].get_ssh_ip()))

        if self._what_to_run_inside.startswith('iperf'):
            for server in servers_per_compute_node[1]:
                server.exe('iperf -s -p 1111 &')
            for server in servers_per_compute_node[2]:
                server.exe('{} -c {} -p 1111'.format(self._what_to_run_inside, servers_per_compute_node[1][0].get_ssh_ip()))

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