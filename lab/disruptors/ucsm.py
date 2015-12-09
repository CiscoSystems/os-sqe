def reboot(context, log, args):
    from fabric.api import settings, run

    log.info('Rebooting...')
    prompt = {'Before rebooting, please take a configuration backup.\nDo you still want to reboot? (yes/no):': 'yes'}
    with settings(host_string='{user}@{ip}'.format(user=context.ucsm_username(), ip=context.ucsm_ip()), password=context.ucsm_password(), connection_attempts=50, warn_only=False):
        run('connect local-mgmt', shell=False)
        with settings(prompts=prompt):
            run('reboot', shell=False)
