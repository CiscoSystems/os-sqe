import lab.nodes.n9


def start(lab, log, args):
    import validators

    name_or_ip = args.get('name_or_ip', 'from_lab')
    is_show_details = args.get('is_show_details', False)

    if validators.ipv4(name_or_ip):
        n9k_ip = name_or_ip
        n9k_username = args['username']
        n9k_password = args['password']
    else:
        n9k_ip, _, n9k_username, n9k_password = lab.n9k_creds()

    nx = lab.nodes.n9.Nexus(n9k_ip, n9k_username, n9k_password)

    port_channels = nx.show_port_channel_summary()

    # Vlans
    vlans = nx.n9_show_vlans()
    log.info('ip={ip} n_vlans={n} {det}'.format(ip=n9k_ip, n=len(vlans),
                                                det='list={0}'.format(vlans) if is_show_details else ''))

    # Allowed vlans
    for port_channel in port_channels:
        allowed_vlans = nx.show_interface_switchport(name=port_channel)
        log.info('ip={ip} service={srv} n_vlans={n} {det}'.format(ip=n9k_ip, srv=port_channel, n=len(allowed_vlans),
                                                                  det='list={0}'.format(allowed_vlans) if is_show_details else ''))
    # User sessions
    if is_show_details:
        users = nx.n9_show_users()
        log.info('ip={ip} n_user_sessions={n} list={l}'.format(ip=n9k_ip, n=len(users), l=users))
