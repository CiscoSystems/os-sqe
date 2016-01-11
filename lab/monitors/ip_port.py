def start(context, log, args):
    import time
    import socket
    import validators

    duration = args['duration']
    period = args['period']
    name_or_ip = args['name_or_ip']
    port = args.get('port', 22)

    if validators.ipv4(name_or_ip):
        ip = name_or_ip
    else:
        ip = str(context.particular_node(name_or_ip).ip)

    down_start = down_end = None

    start_time = time.time()
    while start_time + duration > time.time():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(period/2)
        try:
            s.connect((ip, port))
            res = 1
            if down_start and not down_end:
                down_end = time.time()
        except (socket.timeout, socket.error):
            res = 0
            if not down_start:
                down_start = time.time()
        finally:
            s.close()
        log.info('host={name}:{port} ip={ip} status={status}'.format(name=name_or_ip, port=port, ip=ip, status=res))

        time.sleep(period)

    if down_start:
        if down_end:
            log.info('host={0}:{1} -> downtime={2} secs from={3} to={4}'.format(name_or_ip, port, down_end - down_start, down_start, down_end))
        else:
            log.info('host={0}:{1} -> downtime from={2} and still down when monitor is finished'.format(name_or_ip, port, down_start))
    else:
        log.info('host={0}:{1} -> status=always_up'.format(name_or_ip, port))
