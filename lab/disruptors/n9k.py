def start(lab, log, args):
    from lab.providers.n9k import Nexus

    ip, _, username, password = lab.n9k_creds()
    nx = Nexus(ip, username, password)
    log.ingo('ip={ip} status=rebooting'.format())
    nx.cmd(commands=['reload force'])
