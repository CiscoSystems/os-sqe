from lab.server import Server


class CimcServer(Server):
    _handle = None
    _dump_xml = True
    _logout_on_each_command = False
    LOM_ENABLED, LOM_DISABLED = 'Enabled', 'Disabled'
    POWER_UP, POWER_DOWN, POWER_CYCLE = 'up', 'down', 'cycle-immediate'

    def do_login(self):
        import ImcSdk
        from lab.logger import lab_logger

        lab_logger.info('Logging into CIMC')
        self._handle = ImcSdk.ImcHandle()
        if not all([self._ipmi_ip, self._ipmp_username, self._ipmi_password]):
            raise AttributeError('To control CIMC you need to provide IPMI IP, username and password.')
        self._handle.login(name=self._ipmi_ip, username=self._ipmp_username, password=self._ipmi_password, dump_xml=self._dump_xml)

    def do_logout(self):
        from lab.logger import lab_logger

        lab_logger.info('Logging out from the CIMC')
        self._handle.logout()
        self._handle = None

    def cmd(self, cmd, in_mo=None, class_id=None, params=None):
        from ImcSdk.ImcCoreMeta import ImcException
        from lab.logger import lab_logger

        if not self._handle:
            self.do_login()
        func = getattr(self._handle, cmd)
        try:
            result = func(in_mo=in_mo, class_id=class_id, params=params, dump_xml=self._dump_xml)
        except ImcException as error:
            if error.error_code == '552':
                lab_logger.info('Refreshing connection to CIMC')
                self._handle.refresh(auto_relogin=True)
                result = func(in_mo=in_mo, class_id=class_id, params=params, dump_xml=self._dump_xml)
            else:
                raise
        finally:
            if self._logout_on_each_command:
                self.do_logout()
        return result

    def switch_lom_ports(self, status):
        from lab.logger import lab_logger

        lab_logger.info('Set all LOM ports to the status: {0}'.format(status))
        params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': status}
        self.cmd('set_imc_managedobject', in_mo=None, class_id='BiosVfLOMPortOptionROM', params=params)

    def delete_all_vnics(self):
        from lab.logger import lab_logger

        lab_logger.info('Cleaning up all VNICs from the server')
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
        from lab.logger import lab_logger

        lab_logger.info('Updating boot order. Setting PXE as #{0}, and HDD as #{1}'.format(pxe_order, hdd_order))
        boot_configs = [{'params': {'Dn': 'sys/rack-unit-1/boot-policy/lan-read-only', 'Order': pxe_order, 'Access': 'read-only'},
                         'class_id': 'LsbootLan'},
                        {'params': {'Dn': 'sys/rack-unit-1/boot-policy/storage-read-write', 'Order': hdd_order, 'Access': 'read-write'},
                         'class_id': 'LsbootStorage'}]
        for boot_config in boot_configs:
            boot_device = self.cmd('get_imc_managedobject', in_mo=None, class_id=None, params={'Dn': boot_config['params']['Dn']})
            if boot_device:
                self.cmd('set_imc_managedobject', in_mo=boot_device, class_id=None, params=boot_config['params'])
            else:
                self.cmd('add_imc_managedobject', in_mo=None, class_id=boot_config['class_id'], params=boot_config['params'])

    def create_vnic(self, pci_slot_id, nic_order, nic, native_vlan, params):
        from lab.logger import lab_logger

        lab_logger.info('Creating VNIC on slot {0}. Name={1}, order={2}, native VLAN={3}'.format(pci_slot_id, nic.get_name(), nic_order, native_vlan))
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

    def get_power_status(self):
        return self.cmd('get_imc_managedobject', in_mo=None, class_id='computeRackUnit')[0].get_attr('OperPower')

    def power(self, state=POWER_UP):
        from lab.logger import lab_logger
        import time

        current_power_state = self.get_power_status()
        if current_power_state == 'off' and state == self.POWER_CYCLE:
            state = self.POWER_UP
        if (current_power_state == 'off' and state == self.POWER_UP) or (current_power_state == 'on' and state == self.POWER_DOWN) \
                or state == self.POWER_CYCLE:
            lab_logger.info('Changing power state on server to {0}'.format(state))
            params = {'dn': "sys/rack-unit-1", 'adminPower': state}
            self.cmd('set_imc_managedobject', in_mo=None, class_id='computeRackUnit', params=params)
            time.sleep(120)  # wait for the server to come up

    def cleanup(self):
        from lab.logger import lab_logger

        lab_logger.info('Cleaning CIMC {0}'.format(self))
        self.do_login()
        self.switch_lom_ports(self.LOM_ENABLED)
        self.delete_all_vnics()
        self.power(self.POWER_DOWN)
        self.do_logout()

    def configure_for_osp7(self):
        from lab.logger import lab_logger

        lab_logger.info('Configuring CIMC in {0}'.format(self))
        self.do_login()
        self.power(self.POWER_UP)
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
