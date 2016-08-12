from vts_tests.lib import vtf_connect, base_test


class TestSanity(base_test.BaseTest):

    def test_BondEthernet0_up(self):
        for compute in self.config.computes:
            vtf = vtf_connect.VtfConnect(self.config.build_node, compute)
            self.assertTrue(vtf.is_BondEthernet0_up(), 'BondEthernet0 is up. Compute {0}'.format(compute['ip']))

    def test_ip_fib_output_is_not_empty(self):
        for compute in self.config.computes:
            vtf = vtf_connect.VtfConnect(self.config.build_node, compute)
            self.assertNotEqual(vtf.show_ip_fib(), '', '"ip fib" output is not empty')

    def test_all_vtf_are_reachable_from_xrnc(self):
        vfg = self.vtc_ui.get_virtual_forwarding_groups()

        self.assertGreater(len(vfg['functionalGroup']['vtfs']), 0, 'No VTFs if VFG group')

        def assert_vtf_is_reacahble_from_xrnc(xrnc):
            failed_vtfs = []
            for vtf in vfg['functionalGroup']['vtfs']:
                vtf_ip = vtf['ip']
                if not xrnc.ping(vtf_ip):
                    failed_vtfs.append(vtf_ip)
            self.assertEqual(len(failed_vtfs), 0, 'Several VTFs are not available: [{0}] from xrnc'.format(failed_vtfs, xrnc))

        assert_vtf_is_reacahble_from_xrnc(self.xrnc1)
        if self.xrnc2:
            assert_vtf_is_reacahble_from_xrnc(self.xrnc2)

    def test_xrnc_dl_vts_reg_process_is_running(self):
        def assert_xrnc_dl_vts_reg_process_is_running(xrnc):
            proc_id = xrnc.run('pgrep -f dl_vts_reg.py')
            self.assertNotEqual(proc_id, '', 'dl_vts_reg.py is not running')

        assert_xrnc_dl_vts_reg_process_is_running(self.xrnc1)
        if self.xrnc2:
            assert_xrnc_dl_vts_reg_process_is_running(self.xrnc2)

    def test_dl_server_process_is_running(self):
        proc_id = self.xrnc1.run('pgrep -fdl_server.py')
        self.assertNotEqual(proc_id, '', 'dl_server.py is not running')

    def vni_pool_exists_in_vtc(self):
        vni_pools = self.vtc_ui.get_vni_pools()
        self.assertNotEqual(len(vni_pools), 0, 'VNI Pool is not specified in VTC')

    def test_xrvr_bgp_params(self):
        xrvrs = self.vtc_ui.get_network_inventory_xrvr()
        self.assertNotEqual(len(xrvrs), 0, 'XRVR does not exist')

        for ni in xrvrs:
            self.assertEqual(ni['device_role'], 'leaf', 'Device role is not "leaf". {0}'.format(ni))
            self.assertNotEqual(ni['bgp_asn'], '', 'BGP-ASN is not set. {0}'.format(ni))
            self.assertNotEqual(ni['loopback_if_num'], '', 'Loopback interface is not set. {0}'.format(ni))
            self.assertNotEqual(ni['loopback_if_ip'], '', 'IP of loopback interface is not set. {0}'.format(ni))
