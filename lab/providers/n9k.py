from fabric.api import task


def allow_feature_nxapi(n9k_creds):
    from fabric.api import settings, run

    with settings(host_string='{user}@{ip}'.format(user=n9k_creds['username'], ip=n9k_creds['host']), password=n9k_creds['password']):
        if 'disabled'in run('sh feature | i nxapi', shell=False):
            run('conf t ; feature nxapi', shell=False)


def nxapi(n9k_creds, commands):
    import requests
    import json

    request = [{"jsonrpc": "2.0", "method": "cli", "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
    try:
        results = requests.post('http://{0}/ins'.format(n9k_creds['host']), auth=(n9k_creds['username'], n9k_creds['password']),
                                headers={'content-type': 'application/json-rpc'}, data=json.dumps(request)).json()
        for i, x in enumerate(results, start=0):
            if 'error' in x:
                raise Exception('Error: {0} in command: {1}'.format(x['error']['data']['msg'].strip('\n'), commands[i]))
        return results
    except requests.exceptions.ConnectionError:
        allow_feature_nxapi(n9k_creds)
        nxapi(n9k_creds=n9k_creds, commands=commands)


@task
def configure_for_osp7(yaml_path):
    """configures n9k to run on top of UCSM"""
    from lab.WithConfig import read_config_from_file

    config = read_config_from_file(yaml_path=yaml_path)
    n9k_creds = config['n9k']
    user_vlan = config['user-net']['vlan']

    n9k_creds['host'] = execute_on_given_n9k(n9k_creds=n9k_creds, user_vlan=user_vlan)
    execute_on_given_n9k(n9k_creds=n9k_creds, user_vlan=user_vlan)


def execute_on_given_n9k(n9k_creds, user_vlan):
    from lab.logger import lab_logger

    ports_n9k = []
    ports_fi_a = []
    ports_fi_b = []
    ports_tor = []
    peer_n9k_ip = None

    cdp_neis = nxapi(n9k_creds=n9k_creds, commands=['sh cdp nei det'])
    for nei in cdp_neis['result']['body'][u'TABLE_cdp_neighbor_detail_info'][u'ROW_cdp_neighbor_detail_info']:
        port_id = nei['intf_id']
        if 'TOR' in nei['device_id']:
            ports_tor.append(port_id)
        if 'UCS-FI' in nei['platform_id']:
            if '-A' in nei['device_id']:
                ports_fi_a.append(port_id)
            if '-B' in nei['device_id']:
                ports_fi_b.append(port_id)
        if 'N9K' in nei['platform_id']:
                ports_n9k.append(port_id)
                peer_n9k_ip = nei['v4mgmtaddr']

    def print_or_raise(title, ports_lst):
        if ports:
            lab_logger.info('{0} connected to {1} on {2}'.format(title, ports_lst, n9k_creds['host']))
        else:
            raise Exception('No ports connected to {0} on {1} found!'.format(title, n9k_creds['host']))

    print_or_raise(title='FI-A', ports_lst=ports_fi_a)
    print_or_raise(title='FI-B', ports_lst=ports_fi_b)
    print_or_raise(title='N9K', ports_lst=ports_n9k)
    print_or_raise(title='TOR', ports_lst=ports_tor)

    pcs = nxapi(n9k_creds=n9k_creds, commands=['sh port-channel summary'])
    if pcs['result']:
        pc_ids = []
        dict_or_list = pcs['result']['body'][u'TABLE_channel'][u'ROW_channel']
        if isinstance(dict_or_list, dict):
            pc_ids.append(dict_or_list['group'])
        else:
            pc_ids = [x['group'] for x in dict_or_list]
        for pc_id in pc_ids:
            nxapi(n9k_creds=n9k_creds, commands=['conf t', 'no int port-channel {0}'.format(pc_id)])

    pc_tor, pc_n9k, pc_fi_a, pc_fi_b = 177, 1, ports_fi_a[0].split('/')[-1], ports_fi_b[0].split('/')[-1]

    config = [(ports_n9k, pc_n9k, '1,' + str(user_vlan)),
              (ports_fi_a, pc_fi_a, '1,' + str(user_vlan)),
              (ports_fi_b, pc_fi_b, '1,' + str(user_vlan)),
              (ports_tor, pc_tor, str(user_vlan))]

    nxapi(n9k_creds=n9k_creds, commands=['conf t', 'vlan {0}'.format(user_vlan), 'no shut'])

    for ports, pc_id, vlans in config:
        nxapi(n9k_creds=n9k_creds, commands=['conf t', 'int port-channel {0}'.format(pc_id),
                                             'switchport', 'switchport mode trunk', 'switchport trunk allowed vlan {0}'.format(vlans),
                                             'speed 10000', 'feature lacp'])

    for ports, pc_id, vlans in config:
        nxapi(n9k_creds=n9k_creds, commands=['conf t', 'int ' + ','.join(ports), 'switchport', 'switchport mode trunk',
                                             'switchport trunk allowed vlan {0}'.format(vlans), 'speed 10000',
                                             'channel-group {0} mode active'.format(pc_id)])

    nxapi(n9k_creds=n9k_creds, commands=['conf t', 'feature vpc'])
    nxapi(n9k_creds=n9k_creds, commands=['conf t', 'vpc domain 1', 'peer-keepalive destination {0}'.format(peer_n9k_ip)])
    nxapi(n9k_creds=n9k_creds, commands=['conf t', 'int port-channel {0}'.format(pc_n9k), 'vpc peer-link'])

    for pc_id in [pc_fi_a, pc_fi_b, pc_tor]:
        nxapi(n9k_creds=n9k_creds, commands=['conf t', 'int port-channel {0}'.format(pc_id), 'vpc {0}'.format(pc_id)])

    nxapi(n9k_creds=n9k_creds, commands=['copy run start'])

    return peer_n9k_ip

