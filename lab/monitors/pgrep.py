def start(context, log, args):
    node_name = args['node_name']
    process = args['process']

    server = context.get_node(node_name)
    res = server.run('pgrep {0}'.format(process), warn_only=True)
    log.info('node={0} n_processes={1}'.format(node_name, len(res.split())))
