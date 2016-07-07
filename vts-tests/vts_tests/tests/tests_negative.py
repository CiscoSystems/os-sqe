import datetime
import time
import random

from vts_tests.lib import mercury_node_connect, vtf_connect, base_test


class TestNegative(base_test.BaseTest):

    def test_kill_vpfa_restconf_server_process(self):
        compute = random.choice(self.config.computes)
        compute_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, compute)

        container_id = compute_conn.get_container_id(self.config.CONTAINER_VTF_NAME)
        self.assertNotEqual(container_id, '', 'Container is launched')

        process_id = compute_conn.get_process_id(container_id, self.config.PROCESS_VPFA_NAME)
        self.assertNotEqual(process_id, '', 'vpfa process is running'.format(self.config.PROCESS_VPFA_NAME))
        compute_conn.kill_process_inside_container(container_id, process_id)

        # give it a time to failover
        time.sleep(60)
        container_id = compute_conn.get_container_id(self.config.CONTAINER_VTF_NAME)
        self.assertNotEqual(container_id, '', 'Container is restarted after crash')

        process_id = compute_conn.get_process_id(container_id, self.config.PROCESS_VPFA_NAME)
        self.assertNotEqual(process_id, '', 'vpfa process is running after killing it'.format(self.config.PROCESS_VPFA_NAME))

        self.create_net_subnet_port_instance()
        self.assertTrue(self.instance_status, 'Instance status is not ACTIVE')

    def test_stop_vtf_container(self):
        compute = random.choice(self.config.computes)
        compute_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, compute)

        compute_conn.docker_stop(self.config.CONTAINER_VTF_NAME)

        # give it a time to failover
        time.sleep(2)
        container_id = compute_conn.get_container_id(self.config.CONTAINER_VTF_NAME)
        self.assertNotEqual(container_id, '', 'vtf container is restarted after crash')

        # give it time to start all processes
        time.sleep(30)
        process_id = compute_conn.get_process_id(container_id, self.config.PROCESS_VPFA_NAME)
        self.assertNotEqual(process_id, '', 'vpfa process is running after killing it')

        self.create_net_subnet_port_instance()
        self.assertTrue(self.instance_status, 'Instance status is not ACTIVE')

    def test_reboot_compute_node(self):
        controller = random.choice(self.config.controllers)
        compute = random.choice(self.config.computes)
        compute_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, compute)
        controller_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, controller)

        compute_conn.reboot()
        # Give a time to initiate reboot process. interface should be down to let us track
        # the node state (rebooting/offline?).
        time.sleep(30)

        reboot_timeout = 60 * 5
        reboot_time = datetime.datetime.now()
        while not controller_conn.ping(compute['ip']):
            self.assertLess((datetime.datetime.now() - reboot_time).seconds, reboot_timeout,
                            'Server can not reboot in {0} seconds'.format(reboot_timeout))

        # Give a time to launch containers/processes
        time.sleep(60 * 2)

        compute_conn = mercury_node_connect.MercuryNodeConnect(self.config.build_node, compute)
        container_id = compute_conn.get_container_id(self.config.CONTAINER_VTF_NAME, options='')
        self.assertNotEqual(container_id, '', 'vtf container is running after compute reboot')

        vtf = vtf_connect.VtfConnect(self.config.build_node, compute)
        self.assertTrue(vtf.is_BondEthernet0_up(), 'BondEthernet0 is up. Compute {0}'.format(compute['ip']))
        self.assertNotEqual(vtf.show_ip_fib(), '', '"ip fib" output is not empty')

        self.create_net_subnet_port_instance()
        self.assertTrue(self.instance_status, 'Instance status is not ACTIVE')

    def tearDown(self):
        self.cloud.cleanup()
