def start(context, log, args):
    from fabric.api import run, settings
    import time

    def call_ucsm(command):
        with settings(host_string='{user}@{ip}'.format(user=context.ucsm_username(), ip=context.ucsm_ip()), password=context.ucsm_password(),
                      connection_attempts=1, warn_only=False, timeout=1):
            try:
                return run(command, shell=False, quiet=True).split()
            except:
                return []

    start_time = time.time()

    service_profiles = call_ucsm(command='scope org; sh service-profile status | no-more | egrep -V "Service|----" | cut -f 1 -d " "')
    while start_time + args['duration'] > time.time():
        if args.get('allowed-vlans', False):
            for sp in service_profiles:
                if 'control' in sp or 'compute' in sp:
                    vnic = 'eth0'
                    # Allowed vlans
                    cmd = 'scope org ; scope service-profile {0}; scope vnic {1}; sh eth-if | no-more | egrep "Name:" | cut -f 6 -d " "'.format(sp, vnic)
                    log.info('{0} {1} allowed vlans: {2}'.format(sp, vnic, call_ucsm(command=cmd)))

        # Vlan profiles
        cmd = 'scope eth-uplink; sh vlan | no-more | eg -V "default|VLAN|Name|-----" | cut -f 5 -d " "'
        vlan_profiles = set(call_ucsm(command=cmd))
        log.info('{0} VLANS: {1}'.format(len(vlan_profiles), vlan_profiles))

        # User sessions
        if args.get('user-profile', False):
            user_session = call_ucsm(command='scope security ; show user-sessions local detail | no-more | egrep "Pid:" | cut -f 6 -d " "')
            log.info('{0} user sessions: {1}'.format(len(user_session), user_session))

        time.sleep(args['period'])
