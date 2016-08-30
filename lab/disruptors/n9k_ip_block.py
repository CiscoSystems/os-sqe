def start(context, log, args):
    import time

    duration = args['duration']
    period = 20

    n9k1_ip, n9k2_ip, _, _ = context.n9k_creds()
    log.info('Blocking N9K IPs ({0},{1}) on controllers ...'.format(n9k1_ip, n9k2_ip))

    start_time = time.time()
    for controller in context.controllers():
        controller.exe(command='iptables -A OUTPUT -d {0}/32 -j DROP'.format(n9k1_ip))
        controller.exe(command='iptables -A OUTPUT -d {0}/32 -j DROP'.format(n9k2_ip))
    while start_time + duration > time.time():
        log.info('N9K IPs are blocked.')
        time.sleep(period)

    log.info('Unblocking N9K IPs ({0},{1}) on controllers ...'.format(n9k1_ip, n9k2_ip))
    for controller in context.controllers():
        controller.exe(command='iptables -D OUTPUT -d {0}/32 -j DROP'.format(n9k1_ip))
        controller.exe(command='iptables -D OUTPUT -d {0}/32 -j DROP'.format(n9k2_ip))
