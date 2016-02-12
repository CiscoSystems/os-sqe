from ImcSdk import *
from fabric.api import task
from lab.lab_node import LabNode


class Cimc(LabNode):

    def __init__(self, lab_node_name, ip, username, password, lab):
        self.managed_server = None
        super(Cimc, self).__init__(lab_node_name, ip, username, password, lab)

    def add_managed_server(self, server):
        self.managed_server = server

    def cleanup(self):
        from lab.logger import lab_logger

        lab_logger.info('Cleaning CIMC consoles in lab {0}'.format(self.lab.id))
        handle = ImcHandle()
        for server in self.lab.nodes_controlled_by_cimc():
            handle.login(server.ipmi_creds()[0], server.ipmi_creds()[1], server.ipmi_creds()[2])
            adapters = handle.get_imc_managedobject(None, 'adaptorHostEthIf', dump_xml='true')
            for adapter in adapters:
                if not ('eth0' in adapter.Name or 'eth1' in adapter.Name):
                    try:
                        handle.remove_imc_managedobject(in_mo=None, class_id=adapter.class_id, params={"Dn": adapter.Dn}, dump_xml='true')
                    except ImcException as e:
                        lab_logger.info(e.error_descr)
            params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': 'Enabled'}
            handle.set_imc_managedobject(None, class_id='BiosVfLOMPortOptionROM', params=params, dump_xml='true')
            handle.logout()

    def cmd(self, cmd):
        return NotImplementedError

    def configure_for_osp7(self):
        from lab.logger import lab_logger

        lab_logger.info('Configuring CIMC consoles in lab {0}'.format(self.lab.id))
        handle = ImcHandle()
        for server in self.lab.nodes_controlled_by_cimc()[1:]:
            handle.login(server.ipmi_creds()[0], server.ipmi_creds()[1], server.ipmi_creds()[2])
            params = {'Dn': 'sys/rack-unit-1/bios/bios-settings/LOMPort-OptionROM', 'VpLOMPortsAllState': 'Disabled'}
            handle.set_imc_managedobject(None, class_id='BiosVfLOMPortOptionROM', params=params, dump_xml='true')
            for nic in server.get_nics():
                params = dict()
                params["UplinkPort"] = server.get_cimc()['uplink_port']
                params["dn"] = "sys/rack-unit-1/adaptor-" + str(server.get_cimc()['pci_port']) + "/host-eth-" + nic["nic_name"]
                if 'pxe' in nic["nic_name"]:
                    params['PxeBoot'] = "enabled"
                params['mac'] = nic["nic_mac"]
                params['Name'] = nic["nic_name"]
                if 'eth0' in nic["nic_name"] or 'eth1' in nic["nic_name"]:
                    handle.set_imc_managedobject(None,  'adaptorHostEthIf', params, dump_xml='true')
                else:
                    handle.add_imc_managedobject(None,  'adaptorHostEthIf', params, dump_xml='true')
                general_params = {"Dn": params['dn'] + '/general', AdaptorEthGenProfile.VLAN: nic["nic_vlans"][0], AdaptorEthGenProfile.ORDER: nic["nic_order"]}
                handle.set_imc_managedobject(in_mo=None, class_id="AdaptorEthGenProfile", params=general_params)
            handle.logout()


@task
def cleanup(yaml_path):
    """fab cimc.cleanup:g10 \t\t\t Cleanup all UCSs controlled by CIMC for the given lab.
        :param yaml_path: Valid hardware lab config, usually yaml from $REPO/configs
    """
    cimces = Cimc(yaml_path)
    cimces.cleanup()


@task
def configure_for_osp7(yaml_path):
    """fab cimc.configure_for_osp7:g10 \t\t Configure all UCSs controlled by CIMC for the given lab.
        :param yaml_path: Valid hardware lab config, usually yaml from $REPO/configs
    """
    cimces = Cimc(yaml_path)
    cimces.configure_for_osp7()
