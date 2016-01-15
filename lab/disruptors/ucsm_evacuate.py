def start(context, log, args):

    from fabric.api import settings, run

    fabric = args['fabric']
    # action could be 'start' or 'stop'
    action = args.get('action', 'stop')

    ucsm_ip, ucsm_user, ucsm_password = context.ucsm_creds()

    with settings(host_string='{user}@{ip}'.format(user=ucsm_user, ip=ucsm_ip), password=ucsm_password, connection_attempts=1, timeout=30, warn_only=True):
        cmd = 'scope fabric-interconnect {0} ; {1} server traffic force ; commit-buffer'.format(fabric, action)
        res = run(cmd, shell=False)
        log.info('fabric={0} action={1} result={2}'.format(fabric, action, res.return_code))
