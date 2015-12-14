def start(context, log, args):
    from fabric.api import local
    import time

    down_start = down_end = None
    start_time = time.time()
    while start_time + args['duration'] > time.time():
        ucsm_ip = context.ucsm_ip()
        try:
            local('ping -c 1 -W 1 {0}'.format(ucsm_ip))
            if down_start:
                down_end = time.time()
            log.info('{0} is alive'.format(ucsm_ip))
        except:
            down_start = time.time()
            log.info('{0} is down'.format(ucsm_ip))
        time.sleep(args['period'])
    if down_start:
        log.info('Down time is {0} secs from {1} to {2}'.format(down_end - down_start, down_start, down_end))
