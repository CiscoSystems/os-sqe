def start(lab, log, args):
    import validators
    from lab.vts import Vts

    is_show_details = args.get('is-show-details', False)
    name_or_ip = args.get('name_or_ip', 'from_lab')
    if validators.ipv4(name_or_ip):
        ip = name_or_ip
        username = args['username']
        password = args['password']
        vtc = Vts(name='NotDefined', ip=ip, username=username, password=password, lab=lab, hostname='NoDefined')
    else:
        vtc = lab.get_nodes(Vts)[0]

    vtfs = vtc.get_vtfs()
    log.info('vni-pool={0}'.format(vtc.get_vni_pool()))

    for vtf in vtfs:
        log.info('host={0}; vxlan={1}'.format(vtf, vtf.cmd('show vxlan tunnel')))

    if is_show_details:
        pass

