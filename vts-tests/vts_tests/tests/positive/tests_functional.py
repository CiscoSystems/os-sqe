import random
import unittest

from vts_tests.lib import base_test


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

        if not hasattr(self.cloud, '_keypair_name'):
            self.cloud.create_key_pair()

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
        networks = self.cloud.create_net_subnet(common_part_of_name=random.randint(1, 1000), class_a=10, how_many=5, is_dhcp=False)
        for network_name, network in networks.iteritems():
            prefix = random.randint(1, 1000)
            ports[network_name] = self.cloud.create_ports(instance_name=prefix, on_nets={network_name: network}, is_fixed_ip=True)
            self.cloud.create_instance(name=prefix,
                                       flavor=self.config.flavor,
                                       image=self.config.image_name,
                                       on_ports=ports[network_name])

        for network_name, network in networks.iteritems():
            self.assertTrue(self.vtc_ui.verify_network(network['network']), 'Network synced')
            self.assertTrue(self.vtc_ui.verify_subnet(network['network']['id'], network['subnet']), 'Subnet synced')
            self.assertTrue(self.vtc_ui.verify_ports(network['network']['id'], ports[network_name]), 'Ports synced')
            self.assertTrue(self.vtc_ui.verify_instances(ports[network_name]), 'Instance synced')

    def tearDown(self):
        try:
            self.delete_access_ports()
        except:
            pass
        self.cloud.cleanup()
