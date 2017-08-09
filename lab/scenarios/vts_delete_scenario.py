from lab.parallelworker import ParallelWorker
from lab.decorators import section


class VtsDeleteScenario(ParallelWorker):

    def check_config(self):
        pass

    # noinspection PyAttributeOutsideInit
    @section('Setup')
    def setup_worker(self):
        import collections

        self._n_instances = int(self._kwargs['how-many-servers'])
        self._uptime = int(self._kwargs.get('uptime', 0))
        self._even_server_numbers = [10 + x for x in range(self._n_instances) if x % 2 == 0]
        self._odd_server_numbers = [10 + x for x in range(self._n_instances) if x % 2 != 0]

        self._n_nets = self._kwargs['how-many-networks']
        self._what_to_run_inside = self._kwargs.get('what-to-run-inside', 'Nothing')  # if nothing specified - do not run anything in addition to ping
        self._build_node = self._lab.get_director()
        self._vtc = self._lab.get_vtc()[0]
        self._hosts = self._cloud.os_host_list()
        self._computes = collections.OrderedDict()
        for i, name in enumerate(sorted([x['Host Name'] for x in self._hosts if x['Service'] == 'compute'])):
            self._computes[name] = []
        if len(self._computes) < 2:
            raise RuntimeError('{}: not possible to run on this cloud, number of compute nodes less then 2'.format(self))

        self._cloud.os_cleanup()
        self._flavor = self._cloud.os_flavor_create('vts')
        self._image = self._cloud.os_image_create('iperf')
        self._cloud.os_keypair_create()

        self._even_port_pids = None
        self._odd_port_pids = None

    @section('Creating networks sub-networks and ports')
    def _network_part(self):

        vtc_nets = self._vtc.r_vtc_show_openstack_network()  # should be no sqe-XXX networks
        if len(vtc_nets.keys()) != 1:
            raise RuntimeError('VTC still has some strange networks: {}'.format(vtc_nets))

        self._nets = self._cloud.os_network_create(common_part_of_name='internal', class_a=1, how_many=self._n_nets, is_dhcp=False)
        self._wait_for_vtc_networks()
        self._even_port_pids = self._cloud.os_ports_create(server_numbers=self._even_server_numbers, on_nets=self._nets, is_fixed_ip=True)
        self._odd_port_pids = self._cloud.os_ports_create(server_numbers=self._odd_server_numbers, on_nets=self._nets, is_fixed_ip=True)

    @section('Waiting till VTC registers networks')
    def _wait_for_vtc_networks(self):
        import time

        required = {x['network']['id']: x['network']['provider:segmentation_id'] for x in self._nets.values()}
        max_retries = 10
        while True:
            vtc_nets = self._vtc.r_vtc_show_openstack_network()
            actual = {x['id']: x['provider-segmentation-id'] for x in vtc_nets['collection']['cisco-vts-openstack:network']} if 'collection' in vtc_nets else {}
            if required == actual:
                return
            if max_retries == 0:
                raise RuntimeError('VTC failed to register networks')
            time.sleep(5)
            max_retries -= 1

    @section('Creating instances')
    def _instances_part(self):
        self.log('Creating instances={} status=requested ...'.format(self._even_server_numbers))
        server_info = self._cloud.os_servers_create(server_numbers=self._even_server_numbers, flavor=self._flavor, image=self._image, zone=self._computes.keys()[0], on_ports=self._even_port_pids)
        self.log('instances={} status=created'.format(self._even_server_numbers))

        if self._odd_server_numbers:
            self.log('instances={} status=requested'.format(self._odd_server_numbers))
            server_info += self._cloud.os_servers_create(server_numbers=self._odd_server_numbers, flavor=self._flavor, image=self._image, zone=self._computes.keys()[1], on_ports=self._odd_port_pids)
            self.log('instances={} status=running'.format(self._odd_server_numbers))
        return server_info

    @section('Creating access point on mgmt node')
    def _access_point(self):
        for net_name, net_info in self._nets.items():
            self._build_node.exe('ip link show br_mgmt.3500 || '
                                 '( ip link add link br_mgmt name br_mgmt.3500 type vlan id 3500 && '
                                 'ip link set dev br_mgmt.3500 up && '
                                 'ip address add 1.1.255.254/24 dev br_mgmt.3500 )')

    @section('Pinging instances')
    def _ping_part(self, servers):
        for server in servers:
            n_packets = 50
            ans = self._build_node.exe('ping -c {} {}'.format(n_packets, server.get_ssh_ip()), is_warn_only=True)
            if '{0} packets transmitted, {0} received, 0% packet loss'.format(n_packets) not in ans:
                raise RuntimeError(ans)

    @section('Running iperf')
    def _iperf_part(self):
        answers = []
        for i in range(self._n_instances / 2):
            server = self._computes[0]['servers'][i]
            server.exe('iperf -s -p 1111 &')
        for i in range(self._n_instances / 2):
            server = self._computes[1]['servers'][i]
            ip = self._computes[0]['servers'][i].get_ssh_ip()
            answers.append(server.exe('{} -c {} -p 1111'.format(self._what_to_run_inside, ip)))

    @section('Running test')
    def loop_worker(self):
        import datetime
        import time

        start_time = datetime.datetime.now()

        self._network_part()
        server_info = self._instances_part()
        elapsed_time = (datetime.datetime.now() - start_time).seconds
        self.log('Instances created in [{seconds}] seconds'.format(seconds=elapsed_time))
        if elapsed_time > self._uptime:
            raise Exception('Could not create instances in [{seconds}] seconds. Increase "uptime" parameter or reduce instance/network/etc parameters'.format(seconds=self._uptime))

        if self._uptime > 0:
            sleep_time = self._uptime - elapsed_time
            self.log('Wait for [{seconds}] seconds'.format(seconds=sleep_time))
            time.sleep(sleep_time)

        start_delete_time = datetime.datetime.now()
        for info in server_info:
            self._cloud.os_server_delete(name=info['Name'])
        self.log('Instances deleted in [{seconds}] seconds'.format(seconds=(datetime.datetime.now() - start_delete_time).seconds))

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