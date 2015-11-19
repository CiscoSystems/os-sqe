from fabric.api import task
from lab.time_func import time_as_string


@task
def configure_for_osp7(yaml_path):
    from netaddr import IPNetwork
    import xmlrpclib
    from lab.WithConfig import read_config_from_file
    from lab.providers import ucsm

    config = read_config_from_file(yaml_path=yaml_path)

    cobbler_host = config['cobbler']['host']
    cobbler_username = config['cobbler']['username']
    cobbler_password = config['cobbler']['password']

    user_net = IPNetwork(config['nets']['user']['cidr'])

    ucsm_info = ucsm.read_config_ssh(yaml_path=yaml_path)
    server = ucsm_info['director']

    ipmi_ip = str(server.ipmi['ip'])
    ipmi_username = server.ipmi['username']
    ipmi_password = server.ipmi['password']

    cobbler = xmlrpclib.Server(uri="http://{host}/cobbler_api".format(host=cobbler_host))

    token = cobbler.login(cobbler_username, cobbler_password)
    handle = cobbler.get_system_handle('G{0}-DIRECTOR'.format(config['lab-id']), token)

    cobbler.modify_system(handle, 'comment', 'This system is created by {0} for LAB{1} at {2}'.format(__file__, config['lab-id'], time_as_string()), token)
    cobbler.modify_system(handle, 'hostname', 'g{0}-director.ctocllab.cisco.com'.format(config['lab-id']), token)
    cobbler.modify_system(handle, 'gateway', str(user_net[1]), token)

    for iface, mac in server.get_mac('all').iteritems():
        cobbler.modify_system(handle, 'modify_interface', {'macaddress-{0}'.format(iface): mac}, token)
        if iface == 'user':
            cobbler.modify_system(handle, 'modify_interface', {'ipaddress-{0}'.format(iface): str(user_net[config['nodes']['director']['ip-shift'][0]]),
                                                               'static-{0}'.format(iface): True,
                                                               'subnet-{0}'.format(iface): str(user_net.netmask)}, token)

    cobbler.modify_system(handle, 'power_address', ipmi_ip, token)
    cobbler.modify_system(handle, 'power_user', ipmi_username, token)
    cobbler.modify_system(handle, 'power_pass', ipmi_password, token)
