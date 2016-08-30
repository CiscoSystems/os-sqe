def start(lab, log, args):
    import validators
    from lab.nodes import fi

    is_show_details = args.get('is-show-details', False)
    name_or_ip = args.get('name_or_ip', 'from_lab')
    if validators.ipv4(name_or_ip):
        ucsm_ip = name_or_ip
        ucsm_username = args['username']
        ucsm_password = args['password']
        fi = fi.FI(name='NotDefined', ip=ucsm_ip, username=ucsm_username, password=ucsm_password, lab=lab, hostname='NoDefined')
    else:
        fi = lab.get_nodes_by_class(fi.FI)[0]

    vlan_profiles = sorted([x.split()[0] for x in fi.list_vlans()])
    log.info('n_vlans={0} {1}'.format(len(vlan_profiles), 'details={0}'.format('+'.join(vlan_profiles)) if is_show_details else ''))

    if is_show_details:
        user_sessions = fi.list_user_sessions()
        log.info('n_sessions={0} details={1}'.format(len(user_sessions), '+'.join(user_sessions)))

        service_profiles = [x.split()[0] for x in fi.list_service_profiles()]

        for sp in service_profiles:
            if 'control' in sp or 'compute' in sp:
                vlans_on_profile = [x.split(':')[-1].strip() for x in fi.list_allowed_vlans(sp, 'eth0')]
                log.info('profile=eth0@{sp} n_vlans_on_profile={n} details={vlans}'.format(sp=sp, n=len(vlans_on_profile), vlans='+'.join(vlans_on_profile)))

