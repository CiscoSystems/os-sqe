def start(context, log, args):
    import time
    import socket

    port = args['port']
    period = args['period']
    server = context.partirular_node(args['what'])
    log.info('Starting monitoring {0} port: {1}'.format(server, port))

    start_time = time.time()
    while start_time + args['duration'] > time.time():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(period/2)
        try:
            s.connect((server.ip, port))
            res = 1
        except (socket.timeout, socket.error):
            res = 0
        finally:
            s.close()

        log.info('{0}:{1} Result {2}'.format(server, port, res))

        time.sleep(args['period'])
