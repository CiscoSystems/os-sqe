def monitor(context, log, args):
    from fabric.api import run, settings
    import time

    ucsm_name = 'UCSM-G{0}'.format(context.lab_id())

    def call_ucsm(command):
        with settings(host_string='{user}@{ip}'.format(user=context.ucsm_username(), ip=context.ucsm_ip()), password=context.ucsm_password(), connection_attempts=50, warn_only=False):
            return run(command, shell=False).split()

    log.info('Starting UCSM monitoring {0}'.format(ucsm_name))
    start_time = time.time()

    service_profiles = call_ucsm(command='scope org; sh service-profile status | no-more | egrep -V "Service|----" | cut -f 1 -d " "')
    while start_time + args['duration'] > time.time():
        for sp in service_profiles:
            if 'control' in sp or 'compute' in sp:
                log.info('{0}: {1}'.format(sp, call_ucsm(command='scope org ; scope service-profile {0}; scope vnic eth0; sh eth-if | no-more | egrep "VLAN ID:" | cut -f 7 -d " "'.format(sp))))
        time.sleep(args['period'])
