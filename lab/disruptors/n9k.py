def start(lab, log, args):
    from lab.nodes.n9 import N9

    ip, _, username, password = lab.n9k_creds()
    nx = N9(ip, username, password)
    log.info('ip={ip} status=rebooting'.format(ip=ip))
    nx.cmd(commands=['reload force'])
