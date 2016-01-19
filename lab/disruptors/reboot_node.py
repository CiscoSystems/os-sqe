def start(context, log, args):

    node = context.particular_node(args["node_name"])
    log.info('node={0} status=reboot'.format(node.name))
    context.director().run("ipmitool -I lanplus  -H {host} -U {user}  -P {password} power reset cold".
                           format(host=node.ipmi["ip"], user=node.ipmi["username"], password=node.ipmi["password"]))
