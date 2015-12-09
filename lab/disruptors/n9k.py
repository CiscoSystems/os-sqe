def reboot(context, log, args):
    from lab.providers.n9k import nxapi

    log.ingo('Rebooting...')
    nxapi(n9k_creds=context.n9k_creds(), commands=['reload force'])
