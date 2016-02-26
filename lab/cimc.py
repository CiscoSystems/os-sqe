from lab.server import Server


class CimcServer(Server):
    _handle = None
    _dump_xml = True
    _logout_on_each_command = False
    LOM_ENABLED, LOM_DISABLED = 'Enabled', 'Disabled'

    def do_login(self):
        import ImcSdk

        self._handle = ImcSdk.ImcHandle()
        if not all([self._ipmi_ip, self._ipmp_username, self._ipmi_password]):
            raise AttributeError('To control CIMC you need to provide IPMI IP, username and password.')
        self._handle.login(name=self._ipmi_ip, username=self._ipmp_username, password=self._ipmi_password)

    def do_logout(self):
        self._handle.logout()
        self._handle = None

    def cmd(self, cmd, in_mo=None, class_id=None, params=None):
        if not self._handle:
            self.do_login()
        try:
            result = getattr(self._handle, cmd)(in_mo=in_mo, class_id=class_id, params=params, dump_xml=self._dump_xml)
        finally:
            if self._logout_on_each_command:
                self.do_logout()
        return result

    def switch_lom_ports(self, status):
        params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': status}
        self.cmd('set_imc_managedobject', in_mo=None, class_id='BiosVfLOMPortOptionROM', params=params)

    def delete_all_vnics(self):
        adapters = self.cmd('get_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf')
        for adapter in adapters:
            if adapter.Name not in ['eth0', 'eth1']:
                self.cmd('remove_imc_managedobject', in_mo=None, class_id=adapter.class_id, params={'Dn': adapter.Dn})

    def set_cimc_id(self, server_id):
        pci_bus, n_in_bus = server_id.split('/')  # usually pci_bus/id are the same for all servers, so to make sure macs are different we use here a last octet of ipmi address
        last_ip_octet = str(self._ipmi_ip).split('.')[3]
        self._mac_server_part = 'A{0}:{1:02X}'.format(int(pci_bus), int(last_ip_octet))  # A3:00
        self._form_nics()

    def change_boot_order(self, pxe_order=1, hdd_order=2):
        params = [{'Dn': 'sys/rack-unit-1/boot-policy/lan-read-only', 'Order': pxe_order, 'Access': 'read-only'},
                  {'Dn': 'sys/rack-unit-1/boot-policy/storage-read-write', 'Order': hdd_order, 'Access': 'read-write'}]
        for param in params:
            boot_device = self.cmd('get_imc_managedobject', in_mo=None, class_id=None, params={'Dn': param['Dn']})
            if boot_device:
                self.cmd('set_imc_managedobject', in_mo=boot_device, class_id=None, params=param)
            else:
                self.cmd('add_imc_managedobject', in_mo=None, class_id='LsbootLan', params=param)

    def create_vnic(self, pci_slot_id, nic_order, nic, native_vlan, params):
        params['dn'] = 'sys/rack-unit-1/adaptor-{pci_slot_id}/host-eth-{nic_name}'.format(pci_slot_id=pci_slot_id, nic_name=nic.get_name())
        if 'pxe' in nic.get_name():
            params['PxeBoot'] = 'enabled'
        params['mac'] = nic.get_mac()
        params['Name'] = nic.get_name()
        if params['Name'] in ['eth0', 'eth1']:
            self.cmd('set_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf', params=params)
        else:
            self.cmd('add_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf', params=params)
        general_params = {'Dn': params['dn'] + '/general', 'Vlan': native_vlan, 'Order': nic_order}
        self.cmd('set_imc_managedobject', in_mo=None, class_id="AdaptorEthGenProfile", params=general_params)

    def cleanup(self):
        from lab.logger import lab_logger

        lab_logger.info('Cleaning CIMC {0}'.format(self))
        self.switch_lom_ports(self.LOM_ENABLED)
        self.delete_all_vnics()
        self.do_logout()

    def configure_for_osp7(self):
        from lab.logger import lab_logger

        lab_logger.info('Configuring CIMC in {0}'.format(self))
        self.change_boot_order(pxe_order=1, hdd_order=2)
        self.switch_lom_ports(self.LOM_DISABLED)
        self.delete_all_vnics()
        for wire in self._upstream_wires:
            params = dict()
            pci_slot_id, params['UplinkPort'] = wire.get_port_s().split('/')
            for nic_order, nic in enumerate(self.get_nics()):  # NIC order starts from 0
                native_vlan = self.lab().get_net_vlans(nic.get_name())[0]
                self.create_vnic(pci_slot_id=pci_slot_id, nic_order=nic_order, nic=nic, native_vlan=native_vlan, params=params)
        self.do_logout()
