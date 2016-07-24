import random
import unittest

from vts_tests.lib import base_test


class TestOSInstanceOperations(base_test.BaseTest):

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

    def test_connectivity_same_net_same_compute(self):
        prefix = random.randint(1, 1000)
        networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)
        ports1 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance1, instance_status1 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports1,
                                                                 zone='nova:' + self.compute1['hostname'])
        ports2 = self.cloud.create_ports(instance_name=prefix, on_nets=networks, is_fixed_ip=True)
        instance2, instance_status2 = self.cloud.create_instance(name=prefix,
                                                                 flavor=self.config.flavor,
                                                                 image=self.config.image_name,
                                                                 on_ports=ports2,
                                                                 zone='nova:' + self.compute1['hostname'])

        if self.create_access_ports():
            self.assertTrue(all(self.ping_ports(ports1)), 'Could not reach instance1. Ping failed')
            self.assertTrue(all(self.ping_ports(ports2)), 'Could not reach instance2. Ping failed')

    def tearDown(self):
        try:
            self.delete_access_ports()
        except:
            pass
        self.cloud.cleanup()
