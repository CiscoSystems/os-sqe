def start(context, log, args):
    import time

    node_name = args['node_name']
    process = args['process']
    duration = args['duration']
    period = args['period']

    server = context.particular_node(node_name)
    start_time = time.time()
    while start_time + duration > time.time():
        res = server.run('pgrep {0}'.format(process), warn_only=True)
        log.info('node={0} n_processes={1}'.format(node_name, len(res.split())))
        time.sleep(period)

