def start(lab, log, args):
    from lab.n9k import Nexus

    ip, _, username, password = lab.n9k_creds()
    nx = Nexus(ip, username, password)
    log.info('ip={ip} status=rebooting'.format(ip=ip))
    nx.cmd(commands=['reload force'])
