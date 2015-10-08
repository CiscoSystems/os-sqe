from fabric.api import task
from lab.time import time_as_string


@task
def configure_for_osp7(yaml_path):
    from netaddr import IPNetwork
    import xmlrpclib
    from lab.providers import read_config_from_file
    from lab.providers import ucsm

    config = read_config_from_file(yaml_path=yaml_path)

    lab_id = config['lab-id']

    cobbler_host = config['cobbler']['host']
    cobbler_username = config['cobbler']['username']
    cobbler_password = config['cobbler']['password']
    cobbler_iface_name = config['cobbler']['iface-name']

    ucsm_director_profile_name = config['ucsm']['director-profile']
    user_net = IPNetwork(config['user-net']['cidr'])
    user_iface_name = config['user-net']['iface-name']

    ucsm_info = ucsm.read_config_ssh(host=config['ucsm']['host'], username=config['ucsm']['username'], password=config['ucsm']['password'])
    server = ucsm_info[ucsm_director_profile_name]
    mac_user = server.get_mac(iface_name=user_iface_name)
    mac_cobbler = server.get_mac(iface_name=cobbler_iface_name)

    ipmi_ip = str(server.ipmi['ip'])
    ipmi_username = server.ipmi['username']
    ipmi_password = server.ipmi['password']

    cobbler = xmlrpclib.Server(uri="http://{host}/cobbler_api".format(host=cobbler_host))

    token = cobbler.login(cobbler_username, cobbler_password)
    handle = cobbler.get_system_handle('G{0}-DIRECTOR'.format(lab_id), token)

    cobbler.modify_system(handle, 'comment', 'This system is created by {0} for LAB{1} at {2}'.format(__file__, lab_id, time_as_string()), token)
    cobbler.modify_system(handle, 'hostname', 'g{0}-director.ctocllab.cisco.com'.format(lab_id), token)
    cobbler.modify_system(handle, 'gateway', str(user_net[1]), token)

    cobbler.modify_system(handle, 'modify_interface', {'macaddress-MGMT': mac_user,
                                                       'ipaddress-MGMT': str(user_net[4]),
                                                       'static-MGMT': True,
                                                       'subnet-MGMT': str(user_net.netmask)}, token)
    cobbler.modify_system(handle, 'modify_interface', {'macaddress-PXE-EXT': mac_cobbler}, token)

    cobbler.modify_system(handle, 'power_address', ipmi_ip, token)
    cobbler.modify_system(handle, 'power_user', ipmi_username, token)
    cobbler.modify_system(handle, 'power_pass', ipmi_password, token)
