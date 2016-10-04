from lab.nodes.lab_server import LabServer


class CimcServer(LabServer):
    RAID_0, RAID_1, RAID_10 = '0', '1', '10'

    def __init__(self, node_id, lab, role):
        super(CimcServer, self).__init__(node_id=node_id, lab=lab, role=role)
        self._handle = None
        self._dump_xml = False
        self._logout_on_each_command = False

    def logger(self, message):
        self.log('CIMC ' + message)
        
    def _login(self):
        import ImcSdk

        if self._dump_xml:
            self.logger('logging in')
        self._handle = ImcSdk.ImcHandle()
        oob_ip, oob_username, oob_password = self.get_oob()
        if not all([oob_ip, oob_username, oob_password]):
            raise AttributeError('To control CIMC you need to provide OOB IP, username and password.')
        self._handle.login(name=oob_ip, username=oob_username, password=self._oob_password, dump_xml=self._dump_xml)

    def _logout(self):
        if self._dump_xml:
            self.logger('logging out')
        self._handle.logout()
        self._handle = None

    def cmd(self, cmd, in_mo=None, class_id=None, params=None):
        from ImcSdk.ImcCoreMeta import ImcException
        
        if not self._handle:
            self._login()
        if cmd not in dir(self._handle):
            raise NotImplemented('{} does not exist'.format(cmd))
        func = getattr(self._handle, cmd)
        for i in range(3):  # try to repeat the command up to 3 times
            try:
                return func(in_mo=in_mo, class_id=class_id, params=params, dump_xml=self._dump_xml)
            except ImcException as ex:
                if ex.error_code == '552':
                    self.logger('refreshing connection')
                    self._handle.refresh(auto_relogin=True)
                    continue
                else:
                    raise
            finally:
                if self._logout_on_each_command:
                    self._logout()

    def _cimc_lom(self, status):
        self.logger('{} all LOM'.format(status))
        params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': status, 'vpLOMPort0State': status, 'vpLOMPort1State': status}
        self.cmd('set_imc_managedobject', in_mo=None, class_id='BiosVfLOMPortOptionROM', params=params)

    def cimc_enable_lom(self):
        from time import sleep

        loms = self.cimc_list_lom_ports()
        if not loms:
            self._cimc_lom(status='Enabled')
            self.cimc_power_cycle()
            while True:
                loms = self.cimc_list_lom_ports()
                if loms:
                    self.logger('LOMs are enabled')
                    return
                sleep(20)
        else:
            self.log('LOMs are already enabled')

    def cimc_disable_lom(self):
        self._cimc_lom(status='Disabled')

    def cimc_list_lom_ports(self):
        r = self.cimc_get_mo_by_class_id('networkAdapterEthIf')
        return {'LOM-' + x.Id: {'mac': x.Mac, 'dn': x.Dn} for x in r}

    def cimc_list_vnics(self):
        ans1 = self.cimc_get_mo_by_class_id('adaptorHostEthIf')
        ans2 = self.cimc_get_mo_by_class_id('adaptorEthGenProfile')
        vnics = {x.Name: {'mac': x.Mac, 'uplink': x.UplinkPort, 'pci-slot': x.UsnicCount, 'dn': x.Dn, 'mtu': x.Mtu, 'name': x.Name, 'pxe-boot': x.PxeBoot} for x in ans1}
        vlans_dict = {x.Dn.replace('/general', ''): {'vlan': x.Vlan, 'vlan_mode': x.VlanMode} for x in ans2}
        for vnic in vnics.values():
            vlans = vlans_dict[vnic.get('dn')]
            vnic.update(vlans)
        return vnics

    def cimc_get_mo_by_class_id(self, class_id):
        return self.cmd('get_imc_managedobject', in_mo=None, class_id=class_id)

    def cimc_set_mo_by_class_id(self, class_id, params):
        return self.cmd('set_imc_managedobject', in_mo=None, class_id=class_id, params=params)

    def cimc_enable_sol(self):
        self.logger('enabling SOL')
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
        self.logger('deleting all vNICs')
        vnic_names = self.cimc_list_vnics().keys()
        for vnic_name in vnic_names:
            self.cimc_delete_vnic(vnic_name=vnic_name)

    def cimc_delete_vnic(self, vnic_name):
        dn = 'sys/rack-unit-1/adaptor-MLOM/host-eth-{}'.format(vnic_name)
        if 'eth0' in vnic_name or 'eth1' in vnic_name:  # no way to delete eth0 or eth1, so reset them to default
            self.logger(message='Resetting vNIC ' + vnic_name)
            params = {'UplinkPort': vnic_name[-1], 'mac': 'AUTO', 'mtu': 1500, 'dn': dn}
            self.cimc_set_mo_by_class_id(class_id='adaptorHostEthIf', params=params)
            general_params = {'Dn': dn + '/general', 'Vlan': 'NONE', 'Order': 'ANY'}
            self.cimc_set_mo_by_class_id(class_id='AdaptorEthGenProfile', params=general_params)
        else:
            self.logger(message='Deleting vNIC ' + dn)
            self.cmd('remove_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf', params={'Dn': dn})

    def cimc_set_ssh_timeout(self, timeout=3600):
        self.cmd('set_imc_managedobject', in_mo=None, class_id='commHttps', params={'Dn': 'sys/svc-ext/https-svc', 'sessionTimeout': str(timeout)})

    def cimc_change_boot_order(self, pxe_order=1, hdd_order=2):
        self.logger('updating boot order: PXE as #{0}, HDD as #{1}'.format(pxe_order, hdd_order))
        boot_configs = [{'params': {'Dn': 'sys/rack-unit-1/boot-policy/lan-read-only', 'Order': pxe_order, 'Access': 'read-only'}, 'class_id': 'LsbootLan'},
                        {'params': {'Dn': 'sys/rack-unit-1/boot-policy/storage-read-write', 'Order': hdd_order, 'Access': 'read-write'}, 'class_id': 'LsbootStorage'}]
        for boot_config in boot_configs:
            boot_device = self.cmd('get_imc_managedobject', in_mo=None, class_id=None, params={'Dn': boot_config['params']['Dn']})
            if boot_device:
                self.cmd('set_imc_managedobject', in_mo=boot_device, class_id=None, params=boot_config['params'])
            else:
                self.cmd('add_imc_managedobject', in_mo=None, class_id=boot_config['class_id'], params=boot_config['params'])

    def cimc_create_vnic(self, pci_slot_id, uplink_port, order, name, mac, vlan, is_pxe_enabled):
        self.logger(message='creating vNIC {} on PCI id {} uplink {} mac={} vlan={} pxe: {}'.format(name, pci_slot_id, uplink_port, mac, vlan, is_pxe_enabled))
        params = {'UplinkPort': uplink_port, 'mac': mac, 'Name': name, 'dn': 'sys/rack-unit-1/adaptor-{pci_slot_id}/host-eth-{nic_name}'.format(pci_slot_id=pci_slot_id, nic_name=name)}
        if is_pxe_enabled:
            params['PxeBoot'] = 'enabled'
        if name in ['eth0', 'eth1']:  # eth0 and eth1 are default, only possible to modify there parameters, no way to rename ot delete
            self.cimc_set_mo_by_class_id(class_id='adaptorHostEthIf', params=params)
        else:
            self.cmd('add_imc_managedobject', in_mo=None, class_id='adaptorHostEthIf', params=params)
        general_params = {'Dn': params['dn'] + '/general', 'Vlan': vlan, 'Order': order}
        self.cmd('set_imc_managedobject', in_mo=None, class_id="AdaptorEthGenProfile", params=general_params)

    def cimc_get_power_status(self):
        return self.cimc_get_mo_by_class_id('computeRackUnit')[0].get_attr('OperPower')

    def _cimc_power(self, requested_state):
        import time

        self.logger('power {0}'.format(requested_state))
        self.cmd('set_imc_managedobject', in_mo=None, class_id='computeRackUnit', params={'dn': "sys/rack-unit-1", 'adminPower': requested_state})
        time.sleep(120)  # wait for the server to come up

    def cimc_power_down(self):
        current_power_state = self.cimc_get_power_status()
        if current_power_state == 'on':
            self._cimc_power('down')
        else:
            self.log(' is already OFF')

    def cimc_power_up(self):
        current_power_state = self.cimc_get_power_status()
        if current_power_state == 'off':
            self._cimc_power('up')
        else:
            self.log(' is already ON')

    def cimc_reset(self):
        from ImcSdk.ImcMos import ComputeRackUnit

        #mo = handle.config_resolve_dn("sys/rack-unit-1")

        #mo.admin_power = ComputeRackUnit.CONST_ADMIN_POWER_BMC_RESET_IMMEDIATE
        #set_imc_managedobject(mo, class_id="ComputeRackUnit", params={ComputeRackUnit.ADMIN_POWER:
        #                                                 ComputeRackUnit.CONST_ADMIN_POWER_BMC_RESET_IMMEDIATE,
        #                                             ComputeRackUnit.DN: "sys/rack-unit-1"})

    def cimc_power_cycle(self):
        current_power_state = self.cimc_get_power_status()
        self._cimc_power('up' if current_power_state == 'off' else 'cycle-immediate')

    def cleanup(self):
        self.logger('Cleaning CIMC {0}'.format(self))
        self._login()
        self.cimc_enable_lom()
        self.cimc_delete_all_vnics()
        self.cimc_power_down()
        self._logout()

    def cimc_recreate_vnics(self):
        actual_vnics = self.cimc_list_vnics()
        actual_loms = self.cimc_list_lom_ports()

        for nic_order, nic in enumerate(self.get_nics().values()):  # NIC order starts from 0
            names = nic.get_names()
            macs = nic.get_macs()
            port_ids = nic.get_port_ids()
            for name, mac, port_id in zip(names, macs, port_ids):
                if port_id in ['LOM-1', 'LOM-2']:
                    actual_mac = actual_loms[port_id]['mac']
                    if mac.upper() != actual_mac.upper():
                        raise ValueError('{}: "{}" actual mac is "{}" while requested "{}". Edit lab config!'.format(self.get_id(), port_id, actual_mac, mac))
                else:
                    if 'eth' not in self.get_nics() and nic.is_ssh():  # if no NIC called eth and it's nic on ssh network, use default eth0, eth1
                        if name in actual_vnics:
                            self.cimc_delete_vnic(vnic_name=name)
                        name = 'eth' + name[-1]
                    if name in actual_vnics:
                        if mac == actual_vnics[name]['mac'] and str(nic.get_vlan()) == str(actual_vnics[name]['vlan']):  # this nic is already in CIMC
                            self.logger(message='vNIC {} is already configured'.format(name))
                            if name in actual_vnics:
                                actual_vnics.pop(name)
                            continue
                        else:
                            self.logger('deleting {} since mac or vlan is not correct: {}'.format(name, actual_vnics[name]))
                            self.cimc_delete_vnic(vnic_name=name)
                    pci_slot_id, uplink_port = port_id.split('/')
                    self.cimc_create_vnic(pci_slot_id=pci_slot_id, uplink_port=uplink_port, order='ANY', name=name, mac=mac, vlan=nic.get_vlan(), is_pxe_enabled=nic.is_pxe())
                    if name in actual_vnics:
                        actual_vnics.pop(name)
        for vnic_name in actual_vnics.keys():  # delete all actual which are not requested
            self.cimc_delete_vnic(vnic_name)

    def cimc_configure(self, is_debug=False):
        self._dump_xml = is_debug
        lab_type = self.lab().get_type()
        self.logger('configuring for {}'.format(lab_type))
        self.cimc_power_up()
        is_any_nic_on_lom = any(map(lambda x: x.is_on_lom(), self.get_nics().values()))
        if is_any_nic_on_lom:
            self.cimc_enable_lom()
        self.cimc_recreate_vnics()
        self.cimc_set_hostname()
        self.cimc_change_boot_order(pxe_order=1, hdd_order=2)
        self.cimc_enable_sol()
        # if lab_type == self.lab().LAB_MERCURY:
        #    self.create_storage('1', 2, True)
        self._logout()

    def cimc_get_adapters(self):
        r = self.cimc_get_mo_by_class_id('AdaptorUnit')
        return r

    def cimc_set_mlom_adaptor(self, pci_slot, n_vnics):
        self.logger(message='allowing MLOM-{} to use up to {} vNICs'.format(pci_slot, n_vnics))
        # self.cimc_set_mo_by_class_id(class_id='adaptorUnit', params={'dn': 'sys/rack-unit-1/adaptor-{0}'.format(pci_slot), 'description': str(self)})
        self.cimc_set_mo_by_class_id(class_id='adaptorGenProfile', params={'dn': 'sys/rack-unit-1/adaptor-{0}/general'.format(pci_slot), 'fipMode': 'enabled', 'vntagMode': 'enabled', 'numOfVMFexIfs': n_vnics})

    def cimc_get_mgmt_nic(self):
        r = self.cimc_get_mo_by_class_id('mgmtIf')[0]
        return {'mac': r.Mac, 'ip': r.ExtIp, 'hostname': r.Hostname, 'dn': r.Dn}

    def cimc_set_hostname(self):
        current = self.cimc_get_mgmt_nic()
        new_cimc_hostname = '{}-ru{}-{}'.format(self.lab(), self.get_hardware_info()[0], self.get_id())
        if new_cimc_hostname != current['hostname']:
            self.logger(message='setting hostname to {}'.format(new_cimc_hostname))
            self.cimc_set_mo_by_class_id(class_id='mgmtIf', params={'dn': 'sys/rack-unit-1/mgmt/if-1', 'hostname': new_cimc_hostname})
        else:
            self.logger(message='hostname is already {}'.format(new_cimc_hostname))


class CimcDirector(CimcServer):
    ROLE = 'director-n9'

    def r_get_version(self):
        return self.exe('cat /etc/cisco-mercury-release')

    def r_collect_logs(self, regex):
        body = ''
        for cmd in [self._form_log_grep_cmd(log_files='/var/log/mercury/installer/*', regex=regex)]:
            ans = self.exe(command=cmd, is_warn_only=True)
            body += self._format_single_cmd_output(cmd=cmd, ans=ans)
        return body

    def r_configure_mx_and_nat(self):
        mx_ip, mx_gw_ip = self.get_ip_mx_with_prefix(), self.get_gw_mx_with_prefix()
        self.exe('ip a flush dev br_mgmt')
        self.exe('ip a a {} dev br_mgmt'.format(mx_ip))
        self.exe('ip a a {} dev br_mgmt'.format(mx_gw_ip))
        self.exe('iptables -t nat -A POSTROUTING -o br_api -j MASQUERADE')  # this NAT is only used to access to centralized ceph


class CimcController(CimcServer):
    ROLE = 'control-n9'


class CimcCompute(CimcServer):
    ROLE = 'compute-n9'


class CimcCeph(CimcServer):
    ROLE = 'ceph-n9'
