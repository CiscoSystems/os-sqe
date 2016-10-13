from lab.parallelworker import ParallelWorker


class VtsScenario(ParallelWorker):
    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        import collections

        self._n_instances = int(self._kwargs['how-many-servers'])
        self._even_server_numbers = [10 + x for x in range(self._n_instances) if x % 2 == 0]
        self._odd_server_numbers = [10 + x for x in range(self._n_instances) if x % 2 != 0]

        self._n_nets = self._kwargs['how-many-networks']
        self._what_to_run_inside = self._kwargs.get('what-to-run-inside', 'Nothing')  # if nothing specified - do not run anything in addition to ping
        self._build_node = self._lab.get_director()
        self._hosts = self._cloud.os_host_list()
        self._computes = collections.OrderedDict()
        for i, name in enumerate(sorted([x['Host Name'] for x in self._hosts if x['Service'] == 'compute'])):
            self._computes[name] = []
        if len(self._computes) < 2:
            raise RuntimeError('{}: not possible to run on this cloud, number of compute nodes less then 2'.format(self))
        self._cloud.os_cleanup()
        self._image = self._cloud.os_image_create('iperf')
        self._cloud.os_keypair_create()

    def loop_worker(self):
        from lab.server import Server

        internal_nets = self._cloud.os_network_create(common_part_of_name='internal', class_a=1, how_many=self._n_nets, is_dhcp=False)

        all_servers = []

        even_port_pids = self._cloud.os_ports_create(server_numbers=self._even_server_numbers, on_nets=internal_nets, is_fixed_ip=True)
        odd_port_pids = self._cloud.os_ports_create(server_numbers=self._odd_server_numbers, on_nets=internal_nets, is_fixed_ip=True)

        self._log.info('instances={} status=requested'.format(self._even_server_numbers))
        server_info = self._cloud.os_servers_create(server_numbers=self._even_server_numbers, flavor='m1.medium', image_name=self._image['name'], zone=self._computes.keys()[0], on_ports=even_port_pids)
        self._log.info('instances={} status=created'.format(self._even_server_numbers))

        if self._odd_server_numbers:
            self._log.info('instances={} status=requested'.format(self._odd_server_numbers))
            server_info += self._cloud.os_servers_create(server_numbers=self._odd_server_numbers, flavor='m1.medium', image_name=self._image['name'], zone=self._computes.keys()[1], on_ports=odd_port_pids)
            self._log.info('instances={} status=running'.format(self._odd_server_numbers))

        for info in server_info:
            ip = info['addresses'].split('=')[-1]
            zone = info['OS-EXT-SRV-ATTR:host']
            server = Server(ip=ip, username='admin', password='cisco123')
            self._computes[zone].append(server)
            all_servers.append(server)

        for server in all_servers:
            ans = self._build_node.exe('ping -c5 {}'.format(server.get_ssh_ip()), is_warn_only=True)
            pass

        answers = []
        if self._what_to_run_inside.startswith('iperf'):
            for i in range(self._n_instances / 2):
                server = self._computes[0]['servers'][i]
                server.exe('iperf -s -p 1111 &')
            for i in range(self._n_instances / 2):
                server = self._computes[1]['servers'][i]
                ip = self._computes[0]['servers'][i].get_ssh_ip()
                answers.append(server.exe('{} -c {} -p 1111'.format(self._what_to_run_inside, ip)))
        return answers

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