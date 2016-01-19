def start(lab, log, args):
    import time
    import validators
    from lab.providers import n9k

    duration = args['duration']
    period = args['period']
    name_or_ip = args.get('name_or_ip', 'from_lab')
    is_show_details = args.get('is_show_details', False)

    if validators.ipv4(name_or_ip):
        n9k_ip = name_or_ip
        n9k_username = args['username']
        n9k_password = args['password']
    else:
        n9k_ip, _, n9k_username, n9k_password = lab.n9k_creds()

    nx = n9k.Nexus(n9k_ip, n9k_username, n9k_password)

    port_channels = nx.show_port_channel_summary()

    start_time = time.time()
    finish_time = start_time + duration
    while time.time() < finish_time:
        # Allowed vlans
        for port_channel in port_channels:
            allowed_vlans = nx.show_interface_switchport(name=port_channel)
            log.info('ip={ip} service={srv} n_vlans={n} {det}'.format(ip=n9k_ip, srv=port_channel, n=len(allowed_vlans),
                                                                      det='list={0}'.format(allowed_vlans) if is_show_details else ''))

        # Vlans
        vlans = nx.show_vlan()
        log.info('ip={ip} n_vlans={n} {det}'.format(ip=n9k_ip, n=len(vlans),
                                                    det='list={0}'.format(vlans) if is_show_details else ''))

        # User sessions
        users = nx.show_users()
        log.info('ip={ip} sessions={s}'.format(ip=n9k_ip, s=users))
        time.sleep(period)
        log.info('will finish in {0} secs'. format(finish_time - time.time()))

