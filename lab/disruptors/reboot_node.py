def start(context, log, args):

    node = context.particular_node(args["node_name"])
    wait_time = args.get("timeout", 300)
    log.info('node={0} status=reboot'.format(node.name))
    node.reboot(wait=wait_time)
