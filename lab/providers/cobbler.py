def configure_for_osp7(yaml_path):
    import xmlrpclib
    from lab.laboratory import Laboratory
    from lab.time_func import time_as_string
    from lab.logger import lab_logger

    lab_logger.info('(Re)creating cobbler profile')
    lab = Laboratory(config_path=yaml_path)
    director = lab.director()
    cobbler_host, cobbler_username, cobbler_password = lab.cobbler_creds()

    ipmi_ip, ipmi_username, ipmi_password = director.ipmi_creds()

    cobbler = xmlrpclib.Server(uri="http://{host}/cobbler_api".format(host=cobbler_host))

    token = cobbler.login(cobbler_username, cobbler_password)
    handle = cobbler.get_system_handle('G{0}-DIRECTOR'.format(lab.id), token)

    cobbler.modify_system(handle, 'comment', 'This system is created by {0} for LAB{1} at {2}'.format(__file__, lab.id, time_as_string()), token)
    cobbler.modify_system(handle, 'hostname', director.hostname, token)
    cobbler.modify_system(handle, 'gateway', str(lab.user_gw), token)

    for nic in director.get_nics():
        if_name = nic['nic_name']
        mac = nic['nic_mac']
        cobbler.modify_system(handle, 'modify_interface', {'macaddress-{0}'.format(if_name): mac}, token)
        if if_name == 'user':
            cobbler.modify_system(handle, 'modify_interface', {'ipaddress-{0}'.format(if_name): str(director.ip),
                                                               'static-{0}'.format(if_name): True,
                                                               'subnet-{0}'.format(if_name): str(director.net.netmask)}, token)

    cobbler.modify_system(handle, 'power_address', str(ipmi_ip), token)
    cobbler.modify_system(handle, 'power_user', ipmi_username, token)
    cobbler.modify_system(handle, 'power_pass', ipmi_password, token)
    lab_logger.info('finished')
