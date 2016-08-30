def start(lab, log, args):
    from lab.nodes.n9k import Nexus
    import fabric.network
    import time
    timeout = args.get("timeout", 100)
    ports_on_switch = args["ports_to_shut"].split(',') if "ports_to_shut" in args else map(lambda x: 'po' + x.split(' ')[1], lab.ucsm_uplink_ports())
    n9k1_ip, n9k2_ip, username, password = lab.n9k_creds()
    n9ks = args["n9k_ips"].split(',') if "n9k_ips" in args else [n9k1_ip, n9k2_ip]
    for ip in n9ks:
        nx = Nexus(ip, username, password)
        for port in ports_on_switch:
            log.info('ip={ip} status=switching_off port={port} port_status=off'.format(ip=ip, port=port))
            nx.change_port_state(port_no=port, port_state='shut')
    fabric.network.disconnect_all()
    time.sleep(timeout)
    for ip in n9ks:
        nx = Nexus(ip, username, password)
        for port in ports_on_switch:
            log.info('ip={ip} status=switching_on port={port} port_status=on'.format(ip=ip, port=port))
            nx.change_port_state(port_no=port, port_state='no shut')

