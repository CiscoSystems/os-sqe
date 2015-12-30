def start(context, log, args):
    """
    Watch output of bash cmd
    """
    import time

    node_name = args['node_name']
    cmd = args['cmd']
    name = args.get('name', '')
    duration = args['duration']
    period = args['period']

    server = context.particular_node(node_name)
    start_time = time.time()
    while start_time + duration > time.time():
        res = server.run(cmd, warn_only=True)
        log.info('Node name {0}. Monitor name "{1}". Result {2}.'.format(node_name, name, ''.join(res)))
        time.sleep(period)

