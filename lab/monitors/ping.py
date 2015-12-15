def start(context, log, args):
    from fabric.api import local, settings, hide
    import time

    down_start = down_end = None
    start_time = time.time()
    while start_time + args['duration'] > time.time():
        ucsm_ip = context.ucsm_ip()
        try:
            with settings(warn_only=False):
                with hide('running', 'stdout', 'stderr'):
                    local('ping -c 1 -W 1 {0}'.format(ucsm_ip))
            if down_start and not down_end:
                down_end = time.time()
            log.info('{0} is 1'.format(ucsm_ip))
        except:
            if not down_start:
                down_start = time.time()
            log.info('{0} is 0'.format(ucsm_ip))
        time.sleep(args['period'])
    if down_start:
        if down_end:
            log.info('Down time is {0} secs from {1} to {2}'.format(down_end - down_start, down_start, down_end))
        else:
            log.info('Down time from {0} and still down when monitor is finished'.format(down_start))
