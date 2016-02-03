def start(context, log, args):
    import socket
    import validators

    name_or_ip = args['name_or_ip']
    port = args.get('port', 22)

    if validators.ipv4(name_or_ip):
        ip = name_or_ip
    else:
        ip = str(context.particular_node(name_or_ip).ip)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((ip, port))
        res = 1
    except (socket.timeout, socket.error):
        res = 0
    finally:
        s.close()
    log.info('service={name}:{port} ip={ip} status={status}'.format(name=name_or_ip, port=port, ip=ip, status=res))

