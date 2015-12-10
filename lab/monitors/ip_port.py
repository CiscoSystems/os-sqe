def monitor(context, log, args):
    import time
    import socket

    ip = args['ip']
    port = args['port']
    period = args['period']

    log.info('Starting monitoring ip: {0} port: {1}'.format(ip, port))

    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(period/2)
        try:
            s.connect((ip, port))
            res = 1
        except socket.timeout:
            res = 0
        log.info('IP:port {0}:{1} Result {2}'.format(ip, port, res))

        time.sleep(args['period'])
