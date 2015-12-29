def start(context, log, args):

    node = context.particular_node(args["node_name"])
    log.info('node={0} status=reboot'.format(node.name))
    node.reboot()
