def start(lab, log, args):
    import time
    import validators
    from lab.providers import ucsm

    duration = args['duration']
    period = args['period']
    is_print_vlans = args.get('is-print-vlans', False)
    is_show_details = args.get('is_show_details', False)
    name_or_ip = args.get('name_or_ip', 'from_lab')
    if validators.ipv4():
        ucsm_ip = name_or_ip
        ucsm_username = args['username']
        ucsm_password = args['password']
    else:
        ucsm_ip, ucsm_username, ucsm_password = lab.ucsm_creds()

    fi = ucsm.Ucsm(ucsm_ip, ucsm_username, ucsm_password)

    start_time = time.time()

    service_profiles = fi.service_profiles()
    while start_time + duration > time.time():
        # Vlan profiles
        vlan_profiles = set(fi.vlans())
        log.info('n_vlans={0} {1}'.format(len(vlan_profiles), 'details={0}'.format(vlan_profiles) if is_print_vlans else ''))

        if is_show_details:
            for sp in service_profiles:
                if 'control' in sp or 'compute' in sp:
                    log.info('profile={0} {1} allowed_vlans={2}'.format(sp, 'eth0', fi.allowed_vlans(sp, 'eth0')))

            user_sessions = fi.user_sessions()
            log.info('n_sessions={0} details={1}'.format(len(user_sessions), user_sessions))

        time.sleep(period)
