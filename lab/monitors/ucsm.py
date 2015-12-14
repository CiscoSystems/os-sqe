def monitor(context, log, args):
    from fabric.api import run, settings
    import time

    ucsm_name = 'UCSM-G{0}'.format(context.lab_id())

    def call_ucsm(command):
        with settings(host_string='{user}@{ip}'.format(user=context.ucsm_username(), ip=context.ucsm_ip()), password=context.ucsm_password(), connection_attempts=50, warn_only=True):
            return run(command, shell=False, quiet=True).split()

    log.info('Starting UCSM monitoring {0}'.format(ucsm_name))
    start_time = time.time()

    service_profiles = call_ucsm(command='scope org; sh service-profile status | no-more | egrep -V "Service|----" | cut -f 1 -d " "')
    while start_time + args['duration'] > time.time():
        for sp in service_profiles:
            if 'control' in sp or 'compute' in sp:
                vnic = 'eth0'
                # Allowed vlans
                cmd = 'scope org ; scope service-profile {0}; scope vnic {1}; sh eth-if | no-more | egrep "VLAN ID:" | cut -f 7 -d " "'.format(sp, vnic)
                log.info('{0} {1} allowed vlans: {2}'.format(sp, vnic, call_ucsm(command=cmd)))


        # Vlan profiles
        cmd = 'scope eth-uplink; sh vlan | no-more | eg -V "default|VLAN|Name|-----" | cut -f 5 -d " "'
        vlan_profiles = set(call_ucsm(command=cmd))
        log.info('{0} VLANS: {1}'.format(len(vlan_profiles), vlan_profiles))

        # User sessions
        cmd = 'scope security ; show user-sessions local detail | no-more | egrep "Pid:" | cut -f 6 -d " "'
        log.info('User sessions: {0}'.format(call_ucsm(command=cmd)))

        time.sleep(args['period'])
