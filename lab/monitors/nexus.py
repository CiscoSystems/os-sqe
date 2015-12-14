def start(context, log, args):
    import time
    import logging
    import json
    import requests

    nexus_name = args.get('name', 'Nexus_'.format(args['ip']))

    def _nxapi(commands):
        request = [{"jsonrpc": "2.0", "method": "cli", "params": {"cmd": command, "version": 1}, "id": 1} for command in commands]
        try:
            results = requests.post('http://{0}/ins'.format(args['ip']), auth=(args['username'], args['password']),
                                    headers={'content-type': 'application/json-rpc'}, data=json.dumps(request)).json()
            for i, x in enumerate(results, start=0):
                if 'error' in x:
                    raise Exception('Error: {0} in command: {1}'.format(x['error']['data']['msg'].strip('\n'), commands[i]))
            return results
        except:
            logging.exception("Exception while executing nexus command")
            return {}

    def _make_vlans_set(vlans_str):
        """
        Converts alllowed vlans string to a set object
        :param self:
        :param vlans_str: Ex: 1,177,2006,3000-3004
        :return: Set object {1, 177, 2006, 3000, 3001, 3002, 3003, 3004}
        """
        vlans = set()
        for vlan_range in vlans_str.split(','):
            se = vlan_range.split('-')
            if len(se) == 2:
                vlans = vlans | set(range(int(se[0]), int(se[1]) + 1))
            elif len(se) == 1:
                vlans.add(int(se[0]))
        return vlans

    def _get_item(dictionary, path, default=None):
        """
        Looks for value in dictionary.
        :param dictionary: Source
        :param path: Path to value. List object
        :param default: Default value if there is no such path
        :return: Found value
        """
        d = dictionary
        for i in range(0, len(path) - 1):
            d = d.get(path[i], {})
        return d.get(path[-1], default)

    log.info('Starting NXOS monitoring {0}'.format(nexus_name))
    start_time = time.time()

    port_channels = _get_item(_nxapi(['show port-channel summary']), ['result', 'body', 'TABLE_channel', 'ROW_channel'], [])

    while start_time + args['duration'] > time.time():
        # Allowed vlans
        for port_channel in port_channels:
            pc_name = port_channel['port-channel']
            cmd = 'show interface {0} switchport'.format(pc_name)
            allowed_vlans = _nxapi([cmd])['result']['body']['TABLE_interface']['ROW_interface']['trunk_vlans']
            log.info('{0} {1} Allowed vlans: {2}'.format(nexus_name, pc_name, _make_vlans_set(allowed_vlans)))

        # Vlans
        vlans = _get_item(_nxapi(['show vlan']), ['result', 'body', 'TABLE_vlanbrief', 'ROW_vlanbrief'], [])
        log.info('{0} Vlans: {1}'.format(nexus_name, vlans))

        # User sessions
        users = _get_item(_nxapi(['show users']), ['result', 'body', 'TABLE_sessions', 'ROW_sessions'], [])
        users = [users] if isinstance(users, dict) else users
        log.info('{0} User sessions: {1}'.format(nexus_name, map(lambda u: u['p_pid'], users)))

        time.sleep(args['period'])
