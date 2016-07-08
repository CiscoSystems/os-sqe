import unittest


class TestVtsSanity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from lab.laboratory import Laboratory

        l = Laboratory('g7-2')
        cls._vtc = l.get_node_by_id('vtc1')
        cls._xrvrs = cls._vtc.vtc_get_xrvrs()
        cls._vtfs = cls._vtc.vtc_get_vtfs()

    def test_BondEthernet0_up(self):
        for vtf in self._vtfs:
            self.assertTrue(vtf.is_BondEthernet0_up(), 'BondEthernet0 is up. Compute {0}'.format(vtf))

    def test_ip_fib_output_is_not_empty(self):
        for vtf in self._vtfs:
            self.assertNotEqual(vtf.vtf_show_ip_fib(), '', '"ip fib" output is not empty')

    def test_all_vtf_are_reachable_from_xrnc(self):
        xrvr = self._xrvrs[0]
        vfg = self._vtc.get_virtual_forwarding_groups()

        self.assertGreater(len(vfg['functionalGroup']['vtfs']), 0, 'No VTFs if VFG group')

        failed_vtfs = []
        for vtf in vfg['functionalGroup']['vtfs']:
            vtf_ip = vtf['ip']
            if not xrvr.ping(vtf_ip):
                failed_vtfs.append(vtf_ip)
        self.assertEqual(len(failed_vtfs), 0, 'Several VTFs are not available: [{0}]'.format(failed_vtfs))

    def test_xrnc_dl_vts_reg_process_is_running(self):
        for xrvr in self._xrvrs:
            proc_id = xrvr.cmd('pgrep -f dl_vts_reg.py', is_xrvr=False)
            self.assertNotEqual(proc_id, '', 'dl_vts_reg.py is not running')

    def test_dl_server_process_is_running(self):
        for xrvr in self._xrvrs:
            proc_id = xrvr.cmd('pgrep -fdl_server.py', is_xrvr=False)
            self.assertNotEqual(proc_id, '', 'dl_server.py is not running on {}'.format(xrvr))

    def vni_pool_exists_in_vtc(self):
        vni_pools = self._vtc.vtc_get_vni_pools()
        self.assertNotEqual(len(vni_pools), 0, 'VNI Pool is not specified in VTC')

    def test_xrvr_bgp_params(self):
        net_inventory = self._vtc.vtc_get_network_inventory()
        self.assertNotEqual(len(net_inventory), 0, 'Network inventory is empty')

        device_xrvr_exists = False
        for ni in net_inventory:
            if ni['isxrvr'] == 'true':
                device_xrvr_exists = True
                self.assertEqual(ni['device_role'], 'leaf', 'Device role is not "leaf". {0}'.format(ni))
                self.assertNotEqual(ni['bgp_asn'], '', 'BGP-ASN is not set. {0}'.format(ni))
                self.assertNotEqual(ni['loopback_if_num'], '', 'Loopback interface is not set. {0}'.format(ni))
                self.assertNotEqual(ni['loopback_if_ip'], '', 'IP of loopback interface is not set. {0}'.format(ni))
        self.assertTrue(device_xrvr_exists, 'XRVR does not exist')

    def test_xrnc_mtu_1400_on_br_underlay(self):
        for xrvr in self._xrvrs:
            br_underlay_info = xrvr.cmd('ip -o link show br-underlay', is_xrvr=False)
            self.assertIn('mtu 1400 qdisc', br_underlay_info, '{0} MTU of br_underlay is not set to 1400. Actual state: [{1}]'.format(xrvr, br_underlay_info))

    def test_xrnc_mtu_1400_in_br_underlay_config_file(self):
        for xrvr in self._xrvrs:
            interfaces_config = xrvr.xrnc_get_interfaces_config()
            mtu = "mtu 1400"
            self.assertIn(mtu, interfaces_config['br-underlay'], '{0}: "{1}" is not specified in br-underlay config file'.format(xrvr, mtu))
