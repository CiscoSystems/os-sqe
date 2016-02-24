from lab.server import Server


class CimcServer(Server):
    def set_cimc_id(self, server_id):
        pci_bus, n_in_bus = server_id.split('/')  # usually pci_bus/id are the same for all servers, so to make sure macs are different we use here a last octet of ipmi address
        last_ip_octet = str(self._ipmi_ip).split('.')[3]
        self._mac_server_part = 'A{0}:{1:02X}'.format(int(pci_bus), int(last_ip_octet))  # A3:00
        self._form_nics()

    def cleanup(self):
        import ImcSdk
        from lab.logger import lab_logger

        lab_logger.info('Cleaning CIMC {0} in lab {1}'.format(self._ipmi_ip, self._lab.id))
        handle = ImcSdk.ImcHandle()
        try:
            handle.login(name=self._ipmi_ip, username=self._ipmp_username, password=self._ipmi_password)
            adapters = handle.get_imc_managedobject(None, 'adaptorHostEthIf', dump_xml='true')
            for adapter in adapters:
                if adapter.Name not in ['eth0', 'eth1']:
                    try:
                        handle.remove_imc_managedobject(in_mo=None, class_id=adapter.class_id, params={"Dn": adapter.Dn}, dump_xml='true')
                    except ImcSdk.ImcException as e:
                        lab_logger.info(e.error_descr)
            params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': 'Enabled'}
            handle.set_imc_managedobject(None, class_id='BiosVfLOMPortOptionROM', params=params, dump_xml='true')
        finally:
            handle.logout()

    def cmd(self, cmd):
        return NotImplementedError

    def configure_for_osp7(self):
        import ImcSdk
        from lab.logger import lab_logger

        lab_logger.info('Configuring CIMC consoles in lab {0}'.format(self.lab()))
        handle = ImcSdk.ImcHandle()
        try:
            handle.login(name=self._ipmi_ip, username=self._ipmp_username, password=self._ipmi_password)
            params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': 'Disabled'}
            handle.set_imc_managedobject(None, class_id='BiosVfLOMPortOptionROM', params=params, dump_xml='true')
            for wire in self._upstream_wires:
                params = dict()
                params["UplinkPort"] = wire.get_port_n()
                for nic_order, nic in enumerate(self.get_nics(), start=1):
                    params["dn"] = "sys/rack-unit-1/adaptor-" + str(wire.get_port_s()) + "/host-eth-" + nic.get_name()
                    if 'pxe' in nic.get_name():
                        params['PxeBoot'] = "enabled"
                    params['mac'] = nic.get_mac()
                    params['Name'] = nic.get_name()
                    if params['Name'] in ['eth0', 'eth1']:
                        handle.set_imc_managedobject(None,  'adaptorHostEthIf', params, dump_xml='true')
                    else:
                        handle.add_imc_managedobject(None,  'adaptorHostEthIf', params, dump_xml='true')
                    vlan = 101010  # TODO Eugine- what vlan is meant here?
                    general_params = {"Dn": params['dn'] + '/general', ImcSdk.AdaptorEthGenProfile.VLAN: vlan, ImcSdk.AdaptorEthGenProfile.ORDER: nic_order}
                    handle.set_imc_managedobject(in_mo=None, class_id="AdaptorEthGenProfile", params=general_params)
        finally:
            handle.logout()
