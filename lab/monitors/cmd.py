def start(context, log, args):
    """
    Watch output of bash cmd
    """
    node_name = args['node_name']
    cmd = args['cmd']
    name = args.get('name', '')

    server = context.particular_node(node_name)
    res = server.run(cmd, warn_only=True)
    log.info('node={0}, monitor={1}, result={2}'.format(node_name, name, ''.join(res)))

