import ConfigParser
import inspect
from fabric.api import task, run, local, settings
from lab.with_config import read_config_from_file


@task
def update_conf(original_tempest_conf, output_tempest_conf,
                lab_config, stackrc="/home/stack/stackrc"):
    frame = inspect.currentframe()
    args, _, _, values = inspect.getargvalues(frame)
    if not all(args):
        print """
Ex:
    fab ucsm_tempest_conf.update_conf:/etc/redhat-certification-openstack/tempest.conf,etc/tempest.conf,10.23.228.253,admin,cisco
"""

    ucsm_section = 'ucsm'
    tempest_conf = ConfigParser.RawConfigParser()
    tempest_conf.read(original_tempest_conf)

    config = read_config_from_file(yaml_path=lab_config)
    ucsm_ip = config['ucsm']['host']
    ucsm_user = config['ucsm']['username']
    ucsm_password = config['ucsm']['password']

    ucsm_servers = list()
    nodes = list()

    # Find list of service profiles, servers and macs
    with settings(host_string="{0}@{1}".format(ucsm_user, ucsm_ip), password=ucsm_password):
        profiles = run("show service-profile assoc | egrep Associated | cut -f 1 -d ' '", shell=False).split()
        for profile in profiles:
            server_num = run("scope org ; scope service-profile {0} ; show assoc detail | egrep '^Server:' | cut -f 2 -d ' '".format(profile), shell=False)
            macs = run("scope server {0} ; scope adapter 1 ; show host-eth-if detail | no-more | egrep 'Dynamic MAC Address' | cut -f 8 -d ' '".format(server_num), shell=False).split()
            macs = {mac.lower() for mac in macs}
            ucsm_servers.append({'profile': profile, 'server': server_num, 'macs': macs})
    print "UCSM Servers: ", ucsm_servers

    # Find list of nodes, IP, hostname and MACs of them
    node_names = local("source {0} && nova list | grep ACTIVE | awk '{{print $4}}'".format(stackrc), capture=True).split()
    for node_name in node_names:
        ip = local("nova list | grep {0} | grep -o -P '(?<=ctlplane\=).*? '".format(node_name), capture=True)
        with settings(host_string="{0}@{1}".format('heat-admin', ip), disable_known_hosts=True):
            macs = set(run("ip -o link | grep -o -P '(?<=link\/ether )(.*?) '").split())
        for ucsm_server in ucsm_servers:
            if ucsm_server['macs'] & macs:
                profile = ucsm_server['profile']
                break

        nodes.append({'ip': ip,
                      'hostname': '{0}.localdomain'.format(node_name),
                      'macs': macs,
                      'profile': profile})
    print "Nodes: ", nodes

    ucsm_host_dict = list()
    network_node_list = list()
    for node in nodes:
        ucsm_host_dict.append('{0}:{1}'.format(node['hostname'], node['profile']))
        if 'controll' in node['hostname']:
            network_node_list.append(node['hostname'])

    if not tempest_conf.has_section(ucsm_section):
        tempest_conf.add_section(ucsm_section)
    tempest_conf.set(ucsm_section, 'ucsm_ip', ucsm_ip)
    tempest_conf.set(ucsm_section, 'ucsm_username', ucsm_user)
    tempest_conf.set(ucsm_section, 'ucsm_password', ucsm_password)
    tempest_conf.set(ucsm_section, 'ucsm_host_dict', ','.join(ucsm_host_dict))
    tempest_conf.set(ucsm_section, 'network_node_list', ','.join(network_node_list))
    tempest_conf.set(ucsm_section, 'eth_names', 'eth0,eth1')
    tempest_conf.set(ucsm_section, 'virtual_functions_amount', '4')

    with open(output_tempest_conf, 'w') as f:
        tempest_conf.write(f)
