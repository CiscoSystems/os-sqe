import time

from vts_tests.lib import base_test


class TestOSInstanceOperations(base_test.BaseTest):

    def test_create_network_subnet_port_instance(self):
        self.create_net_subnet_port_instance()
        self.assertTrue(self.instance_status, 'Instance status is not ACTIVE')

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
        self.create_net_subnet_port_instance()
        self.cloud.server_reboot(self.instance['name'], hard=False)
        # TODO: add asserts

    def test_instance_hard_reboot(self):
        self.create_net_subnet_port_instance()
        self.cloud.server_reboot(self.instance['name'], hard=True)
        # TODO: add asserts

    def test_instance_rebuild(self):
        self.create_net_subnet_port_instance()
        self.cloud.server_rebuild(self.instance['name'], image=self.config.image_name)
        # TODO: add asserts

    def test_instance_suspend_resume(self):
        self.create_net_subnet_port_instance()
        self.cloud.server_suspend(self.instance['name'])
        self.cloud.server_resume(self.instance['name'])
        # TODO: add asserts

    def tearDown(self):
        self.cloud.cleanup()
