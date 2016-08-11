import random
import unittest
import time

from vts_tests.lib import base_test, mercury_node_connect, cloud


class TestFunctional(base_test.BaseTest):

    def setUp(self):
        self._skip_if_border_leaf_is_not_configured()

        self.compute1 = None
        self.compute2 = None
        if len(self.config.computes) > 1:
            sample = random.sample(self.config.computes, 2)
            self.compute1 = sample[0]
            self.compute2 = sample[1]
        elif len(self.config.computes) == 1:
            self.compute1 = self.config.computes[0]
        else:
            raise unittest.SkipTest('No computes')

    def _skip_if_border_leaf_is_not_configured(self):
        if not self.config.test_server_cfg:
            raise unittest.SkipTest('Border leaf is not configured. '
                                    'Or you have not updated vts-tests config with border leaf information')

    def _skip_if_one_compute(self):
        if len(self.config.computes) == 1:
            raise unittest.SkipTest('One compute is not enough')

    def assert_instances_reach_each_other(self, ports1, ports2):
        r = self.ping_remote_ports(ports1, ports2)
        self.assertTrue(all(r.values()), 'Could not reach instance2 from instance1. {}'.format(r))

        r = self.ping_remote_ports(ports1, ports2)
        self.assertTrue(all(r.values()), 'Could not reach instance1 from instance2. {}'.format(r))

    def assert_evpn_evi_network_controller(self, vni_number, mac_address, configured=True):
        mac = self.convert_mac(mac_address)
        xrvr_cfg_text = self.xrvr1.run('show run evpn evi {evi} network-controller host mac {mac}'.format(evi=vni_number, mac=mac))
        if configured:
            self.assertNotIn(self.XRVR_NO_SUCH_CONFIGURATION, xrvr_cfg_text, 'XRVR is not configured')
        else:
            self.assertIn(self.XRVR_NO_SUCH_CONFIGURATION, xrvr_cfg_text, 'XRVR is configured')

    def test_connectivity_same_net_same_compute(self):
        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance1, instance_status1 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,
                                                                 compute=self.compute1['hostname'])
        self.assertTrue(instance_status1, 'Instance1 status is not ACTIVE')

        ports2 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance2, instance_status2 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports2,
                                                                 compute=self.compute1['hostname'])
        self.assertTrue(instance_status2, 'Instance2 status is not ACTIVE')

        if not self.create_access_ports():
            raise unittest.SkipTest('Border leaf is not configured')
        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')
        self.assertTrue(all(self.ping_ports(ports2)), 'Could not reach instance2. Ping failed')
        self.assert_instances_reach_each_other(ports1, ports2)

    def test_connectivity_same_net_different_computes(self):
        self._skip_if_one_compute()

        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance1, instance_status1 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,
                                                                 compute=self.compute1['hostname'])
        self.assertTrue(instance_status1, 'Instance1 status is not ACTIVE')

        ports2 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance2, instance_status2 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports2,
                                                                 compute=self.compute2['hostname'])
        self.assertTrue(instance_status2, 'Instance2 status is not ACTIVE')

        if not self.create_access_ports():
            raise unittest.SkipTest('Border leaf is not configured')
        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')
        self.assertTrue(all(self.ping_ports(ports2)), 'Could not reach instance2. Ping failed')
        self.assert_instances_reach_each_other(ports1, ports2)

    def test_connectivity_recreate_port_with_used_mac(self):
        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance, instance_status = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,
                                                                 compute=self.compute1['hostname'])
        self.assertTrue(instance_status, 'Instance status is not ACTIVE')

        if not self.create_access_ports():
            raise unittest.SkipTest('Border leaf is not configured')

        self.assertTrue(all(self.ping_ports(ports1)), 'Can not ping instance.')

        self.cloud.cmd(self.cloud._delete_server_cmd + instance['id'])
        self.cloud.cmd(self.cloud._delete_port_cmd + ports1[0]['id'])

        self.assertFalse(all(self.ping_ports(ports1, attempts=2)), 'Instance is still reachable. But it should be removed.')

        ports2 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True,
                                         ip=self.get_port_ip(ports1[0]), mac=ports1[0]['mac_address'])
        instance, instance_status = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports2,
                                                                 compute=self.compute1['hostname'])
        self.assertTrue(instance_status, 'Instance status is not ACTIVE')
        self.assertTrue(all(self.ping_ports(ports2)), 'Could not reach instance attached to new port with used (early) mac/ip address. Ping failed')

    def test_5_networks_one_instance_per_network_same_tenant(self):
        ports = {}
        vni_numbers = {}
        networks = self.cloud.create_net_subnet(common_part_of_name=random.randint(1, 1000), class_a=10, how_many=5, is_dhcp=False)
        for network_name, network in networks.iteritems():
            prefix = random.randint(1, 1000)
            ports[network_name] = self.cloud.create_ports(instance_name=prefix, on_nets={network_name: network}, is_fixed_ip=True)
            self.cloud.create_instance(name=prefix,
                                       flavor=self.config.flavor,
                                       image=self.config.image_name,
                                       on_ports=ports[network_name])

            vni_numbers[network_name] = self.vtc_ui.get_overlay_network(network['network']['id'])['vni_number']
            self.assert_evpn_evi_network_controller(vni_numbers[network_name], ports[network_name][0]['mac_address'])

        self.cloud.cleanup()
        for network_name, network in networks.iteritems():
            self.assert_evpn_evi_network_controller(vni_numbers[network_name], ports[network_name][0]['mac_address'], configured=False)

    def test_5_networks_one_instance_per_network_different_tenant(self):
        prefix = random.randint(1, 1000)
        vni_vs_mac = {}
        for i in range(5):
            s = str(prefix) + str(i)
            project = self.cloud.project_create(s)
            user = self.cloud.user_create(s, s, project['name'])

            user_cloud = cloud.Cloud(s, user['name'], s, project['name'], end_point=self.cloud.end_point)
            networks = user_cloud.create_net_subnet(common_part_of_name=random.randint(1, 1000), class_a=10, how_many=1, is_dhcp=False)
            for network_name, network in networks.iteritems():
                network_id = network['network']['id']
                ports = user_cloud.create_ports(instance_name=prefix, on_nets={network_name: network}, is_fixed_ip=True)
                user_cloud.create_instance(name=prefix,
                                           flavor=self.config.flavor,
                                           image=self.config.image_name,
                                           on_ports=ports)
                vni_number = self.vtc_ui.get_overlay_network(network_id, project['name'])['vni_number']
                mac = ports[0]['mac_address']
                self.assert_evpn_evi_network_controller(vni_number, mac)

                vni_vs_mac[vni_number] = mac

        self.cloud.cleanup()
        for vni, mac in vni_vs_mac.iteritems():
            self.assert_evpn_evi_network_controller(vni_number, mac, configured=False)

    def test_instance_reachable_if_stop_vtf_container(self):
        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance1, instance_status1 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,
                                                                 compute=self.compute1['hostname'])
        if not self.create_access_ports():
            raise unittest.SkipTest('Border leaf is not configured')
        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')

        compute_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, self.compute1)
        compute_conn.docker_stop(self.config.CONTAINER_VTF_NAME)

        # give it a time to failover
        time.sleep(60)
        container_id = compute_conn.get_container_id(self.config.CONTAINER_VTF_NAME)
        self.assertNotEqual(container_id, '', 'vtf container is not started after stop')
        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')

    def test_instance_reachable_if_restart_vtf_container(self):
        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance1, instance_status1 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,
                                                                 compute=self.compute1['hostname'])
        if not self.create_access_ports():
            raise unittest.SkipTest('Border leaf is not configured')
        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')

        compute_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, self.compute1)
        compute_conn.systemctl_restart_vtf()

        # give it a time to failover
        time.sleep(60)
        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')

    def test_ipv6_ping(self):
        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance1, instance_status1 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,)
        self.assertTrue(instance_status1, 'Instance1 status is not ACTIVE')

        ports2 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance2, instance_status2 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports2)
        self.assertTrue(instance_status2, 'Instance2 status is not ACTIVE')

        if not self.create_access_ports():
            raise unittest.SkipTest('Border leaf is not configured')

        self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')
        self.assertTrue(all(self.ping_ports(ports2)), 'Could not reach instance2. Ping failed')

        ip1v4 = self.get_port_ip(ports1[0])
        ip2v4 = self.get_port_ip(ports2[0])

        ip1v6 = self.get_instance_ipv6_address(ip1v4)
        ip2v6 = self.get_instance_ipv6_address(ip2v4)

        cmd = '/usr/sbin/ping6 -c 4 {ip}'
        self.assertTrue(self.instance_cmd(ip1v4, cmd.format(ip=ip2v6))[0],
                        'Could not reach instance2 from instance1. Ping6 failed')
        self.assertTrue(self.instance_cmd(ip2v4, cmd.format(ip=ip1v6))[0],
                        'Could not reach instance1 from instance2. Ping6 failed')

    def tearDown(self):
        try:
            self.delete_access_ports()
        except:
            pass
        self.cloud.cleanup()
