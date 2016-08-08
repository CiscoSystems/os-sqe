import time
import unittest

from vts_tests.lib import base_test


class TestOSInstanceOperations(base_test.BaseTest):

    def _create_one_instance(self):
        time.sleep(10)
        self.create_net_subnet_port_instance()
        self.assertTrue(self.instance_status, 'Instance status is not ACTIVE')
        if self.create_access_ports():
            self._assert_ping_instance_ports()
        else:
            # TODO: Replace with log message
            print "Could not create ports on the border leaf"

    def _assert_ping_instance_ports(self):
        if self.config.test_server_cfg:
            self.assertTrue(all(self.ping_ports(self.ports)), 'Could not reach instance. Ping failed')
        else:
            # TODO: Replace with warning message
            print "Could not ping instances because  the border leaf is not configured"

    def test_create_network_subnet_port_instance(self):
        self._create_one_instance()
        self.delete_access_ports()

        for network_name, network in self.networks.iteritems():
            self.assertTrue(self.vtc_ui.verify_network(network['network']), 'Network synced')
            self.assertTrue(self.vtc_ui.verify_subnet(network['network']['id'], network['subnet']), 'Subnet synced')
            self.assertTrue(self.vtc_ui.verify_ports(network['network']['id'], self.ports), 'Ports synced')
        self.assertTrue(self.vtc_ui.verify_instances(self.ports), 'Instance synced')

        self.cloud.cleanup()

        # TODO: Remove sleep
        time.sleep(10)

        for p in self.ports:
            self.assertEqual(self.vtc_ui.get_overlay_vm(p['id']), None, 'Instance has been removed')
        for network_name, network in self.networks.iteritems():
            self.assertEqual(self.vtc_ui.get_overlay_network(network['network']['id']), None, 'Network has been removed')

    def test_instance_soft_reboot(self):
        self._create_one_instance()
        self.cloud.server_reboot(self.instance['name'], hard=False)
        self._assert_ping_instance_ports()

    def test_instance_hard_reboot(self):
        self._create_one_instance()
        self.cloud.server_reboot(self.instance['name'], hard=True)
        self._assert_ping_instance_ports()

    def test_instance_rebuild(self):
        self._create_one_instance()
        self.cloud.server_rebuild(self.instance['name'], image=self.config.image_name)
        self._assert_ping_instance_ports()

    def test_instance_suspend_resume(self):
        self._create_one_instance()
        self.cloud.server_suspend(self.instance['name'])
        self.cloud.server_resume(self.instance['name'])
        self._assert_ping_instance_ports()

    def tearDown(self):
        try:
            self.delete_access_ports()
        except:
            pass
        self.cloud.cleanup()
