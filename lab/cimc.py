from lab.server import Server


class CimcServer(Server):
    _handle = None
    _dump_xml = True
    _logout_on_each_command = False
    LOM_ENABLED, LOM_DISABLED = 'Enabled', 'Disabled'
    POWER_UP, POWER_DOWN, POWER_CYCLE = 'up', 'down', 'cycle-immediate'
    RAID_0, RAID_1, RAID_10 = '0', '1', '10'

    def form_mac(self, lab_id, net_octet):
        last_ip_octet = str(self._ipmi_ip).split('.')[3]
        return '{lab:02}:00:A0:{ip:02X}:00:{net}'.format(lab=lab_id, ip=int(last_ip_octet), net=net_octet)

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

    def get_lom_macs(self):
        return map(lambda x: x.Mac, self.get_mo_by_class_id('networkAdapterEthIf'))

    def disable_pxe_all_intf(self, status):
        adapters = self.get_mo_by_class_id('adaptorHostEthIf')
        for adapter in adapters:
            self.switch_lom_ports(status)
            params = dict()
            params['dn'] = adapter.Dn
            params['PxeBoot'] = 'disabled'
            params['mac'] = adapter.Mac
            params['Name'] = adapter.Name
            self.cmd('set_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf', params=params)


    def get_mo_by_class_id(self, class_id):
        return self.cmd('get_imc_managedobject', in_mo=None, class_id=class_id)

    def enable_sol(self):
        from lab.logger import lab_logger

        lab_logger.info('Enable Serial over Lan connections')
        params = {'dn': 'sys/rack-unit-1/sol-if', 'adminState': 'enable', 'speed': '115200'}
        self.cmd('set_imc_managedobject', in_mo=None, class_id='solIf', params=params)

    def create_storage(self, raid=RAID_1, disks_needed=2, clean_vds=False):
        """

        :param clean_vds: Clean all virtual drives before creating any
        :param raid: Please select from '0','1','10','5','6'
        :param disks_needed: Number of disks needed
        :return:
        """
        if raid not in [self.RAID_0, self.RAID_1, self.RAID_10]:
            raise ValueError('RAID request is not correct. Use one of the {0}. Got: {1}'.format(','.join([self.RAID_0, self.RAID_1, self.RAID_10]), raid))
        from lab.logger import lab_logger
        virtual_drives_list = self.get_mo_by_class_id('storageVirtualDrive')
        if virtual_drives_list:
            if clean_vds:
                lab_logger.info('Cleaning Virtual Drives to create new one.')
                for vd in virtual_drives_list:
                    self.cmd('remove_imc_managedobject', in_mo=None, class_id='storageVirtualDrive', params={'Dn': vd.Dn})
            else:
                lab_logger.info('Virtual Drive already exists.')
                return
        disks = self.get_mo_by_class_id('storageLocalDisk')
        # get 2 or more disks to form RAID
        disks_by_size = {}
        map(lambda x: disks_by_size.setdefault(x.get_attr('CoercedSize'), []).append(x), disks)
        available_disks = filter(lambda x: len(disks_by_size[x]) > disks_needed, disks_by_size.keys())
        if len(available_disks) == 0:
            raise Exception('Not enough disks to build RAID {0}. Minimum required are {1}.'.format(raid, disks_needed))
        size = available_disks[0]
        drive_group = ','.join(map(lambda x: x.Id, disks_by_size[size])[:disks_needed])
        params = {'raidLevel': raid, 'size': size, 'virtualDriveName': "RAID", 'dn': "sys/rack-unit-1/board/storage-SAS-SLOT-HBA/virtual-drive-create",
                  'driveGroup': '[{0}]'.format(drive_group), 'adminState': 'trigger', 'writePolicy': 'Write Through'}
        lab_logger.info('Creating Virtual Drive RAID {0}. Using storage {0}'.format(raid, drive_group))
        self.cmd('set_imc_managedobject', in_mo=None, class_id="storageVirtualDriveCreatorUsingUnusedPhysicalDrive", params=params)

    def delete_all_vnics(self):
        from lab.logger import lab_logger

        lab_logger.info('Cleaning up all VNICs from the server')
        adapters = self.get_mo_by_class_id('adaptorHostEthIf')
        for adapter in adapters:
            if adapter.Name not in ['eth0', 'eth1']:
                self.cmd('remove_imc_managedobject', in_mo=None, class_id=adapter.class_id, params={'Dn': adapter.Dn})

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
        return self.get_mo_by_class_id('computeRackUnit')[0].get_attr('OperPower')

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

    def configure_for_mercury(self):
        from lab.logger import lab_logger

        lab_logger.info('Configuring CIMC in {0}'.format(self))
        self.do_login()
        self.power(self.POWER_UP)
        if 'director' not in self._name:
            self.switch_lom_ports(self.LOM_DISABLED)
        self.enable_sol()
        self.create_storage('1', 2, True)
        self.power(self.POWER_CYCLE)

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
