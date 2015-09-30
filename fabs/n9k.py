from fabric.api import task


def nxapi(ip, username, password, commands):
    import requests
    import json

    request = [{"jsonrpc": "2.0", "method": "cli", "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
    return requests.post('http://{0}/ins'.format(ip), data=json.dumps(request), headers={'content-type': 'application/json-rpc'}, auth=(username, password)).json()


@task
def configure_for_osp7(yaml_path):
    """configures n9k to run on top of UCSM"""
    from fabs import read_config_from_file

    config = read_config_from_file(yaml_path=yaml_path)
    n9k_ip = config['n9k']['host']
    n9k_username = config['n9k']['username']
    n9k_password = config['n9k']['password']
    vlan = config['mgmt_vlan']

    all_ports = set()
    all_port_channels = set()
    other_n9k_ips = set()

    cdp_neis = nxapi(ip=n9k_ip, username=n9k_username, password=n9k_password, commands=['sh cdp nei det'])
    for nei in cdp_neis['result']['body'][u'TABLE_cdp_neighbor_detail_info'][u'ROW_cdp_neighbor_detail_info']:
        port_id = nei['intf_id']
        if 'TOR' in nei['device_id']:
                all_ports.add(port_id)
        if 'UCS-FI' in nei['platform_id']:
                all_ports.add(port_id)
        if 'N9K' in nei['platform_id']:
                all_ports.add(port_id)
                other_n9k_ips.add(nei['v4mgmtaddr'])
    pcs = nxapi(ip=n9k_ip, username=n9k_username, password=n9k_password, commands=['sh port-channel summary'])
    for pc in pcs['result']['body'][u'TABLE_channel'][u'ROW_channel']:
        pc_id = pc['port-channel']
        dict_or_list = pc['TABLE_member']['ROW_member']
        if isinstance(dict_or_list, dict):
            participating_iface_ids = [dict_or_list['port']]
        else:
            participating_iface_ids = [x['port'] for x in dict_or_list]
        if any([x in all_ports for x in participating_iface_ids]):
            all_port_channels.add(pc_id)
    nxapi(ip=n9k_ip, username=n9k_username, password=n9k_password, commands=['conf t', 'vlan {0}'.format(vlan), 'no shut'])
    nxapi(ip=n9k_ip, username=n9k_username, password=n9k_password, commands=['conf t', 'int ' + ','.join(all_port_channels), 'switchport trunk allowed vlan add {0}'.format(vlan)])

    for ip in other_n9k_ips:
        nxapi(ip=ip, username=n9k_username, password=n9k_password, commands=['conf t', 'vlan {0}'.format(vlan), 'no shut'])
        nxapi(ip=ip, username=n9k_username, password=n9k_password, commands=['conf t', 'int ' + ','.join(all_port_channels), 'switchport trunk allowed vlan add {0}'.format(vlan)])
