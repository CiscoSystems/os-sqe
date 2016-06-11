from lab.server import Server


class CimcServer(Server):
    _handle = None
    _dump_xml = True
    _logout_on_each_command = False
    LOM_ENABLED, LOM_DISABLED = 'Enabled', 'Disabled'
    POWER_UP, POWER_DOWN, POWER_CYCLE = 'up', 'down', 'cycle-immediate'
    RAID_0, RAID_1, RAID_10 = '0', '1', '10'

    def __init__(self, node_id, lab, role, hostname):
        super(CimcServer, self).__init__(node_id=node_id, lab=lab, role=role, hostname=hostname)
        self._info_cache = {'adaptors': []}

    def logger(self, message):
        from lab.logger import lab_logger

        lab_logger.info('{0}: {1}'.format(self, message))
        
    def form_mac(self, mac_pattern):
        return '00:{lab:02}:A0:{role_id}:{count:02}:{net}'.format(lab=self._lab.get_id(), role_id=self.lab().ROLES[self.get_role()], count=self._n, net=mac_pattern)

    def cimc_login(self):
        import ImcSdk

        self.logger('Logging into CIMC')
        self._handle = ImcSdk.ImcHandle()
        oob_ip, oob_username, oob_password = self.get_oob()
        if not all([oob_ip, oob_username, oob_password]):
            raise AttributeError('To control CIMC you need to provide OOB IP, username and password.')
        self._handle.login(name=oob_ip, username=oob_username, password=self._oob_password, dump_xml=self._dump_xml)

    def cimc_logout(self):
        self.logger('Logging out from the CIMC')
        self._handle.logout()
        self._handle = None

    def cmd(self, cmd, in_mo=None, class_id=None, params=None):
        from ImcSdk.ImcCoreMeta import ImcException
        
        if not self._handle:
            self.cimc_login()
        if cmd not in dir(self._handle):
            raise NotImplemented('{} does not exist'.format(cmd))
        func = getattr(self._handle, cmd)
        for i in range(3):  # try to repeat the command up to 3 times
            try:
                return func(in_mo=in_mo, class_id=class_id, params=params, dump_xml=self._dump_xml)
            except ImcException as error:
                if error.error_code == '552':
                    self.logger('Refreshing connection to CIMC')
                    self._handle.refresh(auto_relogin=True)
                    continue
            finally:
                if self._logout_on_each_command:
                    self.cimc_logout()

    def cimc_switch_lom_ports(self, status):
        self.logger('Set all LOM ports to the status: {0}'.format(status))
        params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': status, 'vpLOMPort0State': status, 'vpLOMPort1State': status}
        self.cmd('set_imc_managedobject', in_mo=None, class_id='BiosVfLOMPortOptionROM', params=params)

    def list_lom_macs(self):
        return map(lambda x: x.Mac, self.cimc_get_mo_by_class_id('networkAdapterEthIf'))

    def list_mlom_macs(self):
        return map(lambda x: x.Mac, self.cimc_get_mo_by_class_id('adaptorHostEthIf'))

    def disable_pxe_all_intf(self, status):
        adapters = self.cimc_get_mo_by_class_id('adaptorHostEthIf')
        for adapter in adapters:
            self.cimc_switch_lom_ports(status)
            params = {'dn': adapter.Dn, 'PxeBoot': 'disabled', 'mac': adapter.Mac, 'Name': adapter.Name}
            self.cimc_set_mo_by_class_id(class_id='adaptorHostEthIf', params=params)

    def cimc_get_mo_by_class_id(self, class_id):
        return self.cmd('get_imc_managedobject', in_mo=None, class_id=class_id)

    def cimc_set_mo_by_class_id(self, class_id, params):
        return self.cmd('set_imc_managedobject', in_mo=None, class_id=class_id, params=params)

    def cimc_enable_sol(self):
        self.logger('Enable Serial over Lan connections')
        params = {'dn': 'sys/rack-unit-1/sol-if', 'adminState': 'enable', 'speed': '115200'}
        self.cimc_set_mo_by_class_id(class_id='solIf', params=params)

    def create_storage(self, raid=RAID_1, disks_needed=2, clean_vds=False):
        """

        :param clean_vds: Clean all virtual drives before creating any
        :param raid: Please select from '0','1','10','5','6'
        :param disks_needed: Number of disks needed
        :return:
        """
        if raid not in [self.RAID_0, self.RAID_1, self.RAID_10]:
            raise ValueError('RAID request is not correct. Use one of the {0}. Got: {1}'.format(','.join([self.RAID_0, self.RAID_1, self.RAID_10]), raid))
        
        virtual_drives_list = self.cimc_get_mo_by_class_id('storageVirtualDrive')
        if virtual_drives_list:
            if clean_vds:
                self.logger('Cleaning Virtual Drives to create new one.')
                for vd in virtual_drives_list:
                    self.cmd('remove_imc_managedobject', in_mo=None, class_id='storageVirtualDrive', params={'Dn': vd.Dn})
            else:
                self.logger('Virtual Drive already exists.')
                return
        disks = self.cimc_get_mo_by_class_id('storageLocalDisk')
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
        self.logger('Creating Virtual Drive RAID {0}. Using storage {0}'.format(raid, drive_group))
        self.cimc_set_mo_by_class_id(class_id="storageVirtualDriveCreatorUsingUnusedPhysicalDrive", params=params)

    def cimc_delete_all_vnics(self):
        self.logger('Cleaning up all VNICs from the server')
        adapters = self.cimc_get_mo_by_class_id('adaptorHostEthIf')
        for adapter in adapters:
            if adapter.Name not in ['eth0', 'eth1']:
                self.cmd('remove_imc_managedobject', in_mo=None, class_id=adapter.class_id, params={'Dn': adapter.Dn})
            else:
                params = {'UplinkPort': adapter.Name[-1], 'mac': 'AUTO', 'mtu': 1500, 'dn': adapter.Dn}
                self.cimc_set_mo_by_class_id(class_id='adaptorHostEthIf', params=params)
                general_params = {'Dn': adapter.Dn + '/general', 'Vlan': 'NONE', 'Order': adapter.Name[-1]}
                self.cimc_set_mo_by_class_id(class_id='AdaptorEthGenProfile', params=general_params)

    def cimc_set_ssh_timeout(self, timeout=3600):
        self.cmd('set_imc_managedobject', in_mo=None, class_id='commHttps', params={'Dn': 'sys/svc-ext/https-svc', 'sessionTimeout': str(timeout)})

    def cimc_change_boot_order(self, pxe_order=1, hdd_order=2):
        self.logger('Updating boot order. Setting PXE as #{0}, and HDD as #{1}'.format(pxe_order, hdd_order))
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

    def cimc_create_vnic(self, pci_slot_id, uplink_port, nic_order, nic, native_vlan):
        if nic.get_name() in ['eth0', 'eth1']:
            corrected_nic_name = nic.get_name()
            corrected_nic_order = nic.get_name()[-1]
            corrected_mac = nic.get_mac()
            corrected_uplink_port = nic.get_name()[-1]
        else:
            corrected_nic_name = nic.get_name() + '-' + str(uplink_port)
            corrected_nic_order = str(5 + 2*int(nic_order) + int(uplink_port))  # started split order from 5
            corrected_mac = nic.get_mac()[:-5] + corrected_nic_order.zfill(2) + nic.get_mac()[-3:]
            corrected_uplink_port = uplink_port

        params = {'UplinkPort': corrected_uplink_port, 'mac': corrected_mac, 'Name': corrected_nic_name,
                  'dn': 'sys/rack-unit-1/adaptor-{pci_slot_id}/host-eth-{nic_name}'.format(pci_slot_id=pci_slot_id, nic_name=corrected_nic_name)}
        if 'pxe' in nic.get_name():
            params['PxeBoot'] = 'enabled'
        if nic.get_name() in ['eth0', 'eth1']:
            self.cimc_set_mo_by_class_id(class_id='adaptorHostEthIf', params=params)
        else:
            self.cmd('add_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf', params=params)
        general_params = {'Dn': params['dn'] + '/general', 'Vlan': native_vlan, 'Order': corrected_nic_order}
        self.cmd('set_imc_managedobject', in_mo=None, class_id="AdaptorEthGenProfile", params=general_params)
        self.logger('Creating VNIC {name} with order={order}, VLAN={vlan}'.format(name=params['Name'], order=corrected_nic_order, vlan=native_vlan))

    def cimc_get_power_status(self):
        return self.cimc_get_mo_by_class_id('computeRackUnit')[0].get_attr('OperPower')

    def cimc_power(self, state=POWER_UP):
        import time

        current_power_state = self.cimc_get_power_status()
        if current_power_state == 'off' and state == self.POWER_CYCLE:
            state = self.POWER_UP
        if (current_power_state == 'off' and state == self.POWER_UP) or (current_power_state == 'on' and state == self.POWER_DOWN) \
                or state == self.POWER_CYCLE:
            self.logger('Changing power state on server to {0}'.format(state))
            params = {'dn': "sys/rack-unit-1", 'adminPower': state}
            self.cmd('set_imc_managedobject', in_mo=None, class_id='computeRackUnit', params=params)
            time.sleep(120)  # wait for the server to come up

    def cleanup(self):
        self.logger('Cleaning CIMC {0}'.format(self))
        self.cimc_login()
        self.cimc_switch_lom_ports(self.LOM_ENABLED)
        self.cimc_delete_all_vnics()
        self.cimc_power(self.POWER_DOWN)
        self.cimc_logout()

    def cimc_recreate_vnics(self):
        self.cimc_delete_all_vnics()
        for nic_order, nic in enumerate(self.get_nics()):  # NIC order starts from 0
            if nic.is_bond():
                native_vlan = nic.get_vlans()[0]
                for wire in self._upstream_wires:
                    pci_slot_id, uplink_port = wire.get_own_port(node=self).split('/')
                    if pci_slot_id not in ['lom', 'LOM']:
                        self.cimc_create_vnic(pci_slot_id=pci_slot_id, uplink_port=uplink_port, nic_order=nic_order, nic=nic, native_vlan=native_vlan)
                    if nic.get_name() in ['eth0', 'eth1']:  # since eth0 and eth1 are special they are not split like user -> user-0, user-1
                        break
            else:
                if nic.get_mac() not in self.list_lom_macs():
                    raise ValueError('Specified MAC {mac} is not on LOM on {srv}. Edit lab config'.format(mac=nic.get_mac(), srv=self))

    def configure(self):
        lab_type = self.lab().get_type(0)
        self.logger('Configuring for {}'.format(lab_type))
        self.cimc_login()
        self.cimc_power(self.POWER_UP)
        self.cimc_set_hostname()
        self.cimc_change_boot_order(pxe_order=1, hdd_order=2)
        if not self.is_deploy_by_cobbler():
            self.cimc_switch_lom_ports(self.LOM_DISABLED)
        self.cimc_enable_sol()
        if lab_type == self.lab().LAB_MERCURY:
            self.create_storage('1', 2, True)
        self.cimc_recreate_vnics()
        self.cimc_logout()

    def cimc_get_adapters(self):
        r = self.cimc_get_mo_by_class_id('AdaptorUnit')[0]
        return r

    def cimc_get_mgmt_nic(self):
        r = self.cimc_get_mo_by_class_id('mgmtIf')[0]
        return {'mac': r.Mac, 'ip': r.ExtIp, 'hostname': r.Hostname}

    def cimc_set_hostname(self):
        ru, _ = self.get_hardware_info()
        return self.cimc_set_mo_by_class_id(class_id='mgmtIf', params={'hostname': '{}-{}'.format(ru, self.get_id())})
