def start(lab, log, args):
    import validators
    from lab.vts import Vts

    is_show_details = args.get('is-show-details', False)
    name_or_ip = args.get('name_or_ip', 'from_lab')
    if validators.ipv4(name_or_ip):
        ip = name_or_ip
        username = args['username']
        password = args['password']
        vts = Vts(name='NotDefined', ip=ip, username=username, password=password, lab=lab, hostname='NoDefined')
    else:
        vts = lab.get_vtc()[0]

    vni_pool = vts.get_vni_pool()
    log.info('vni={0}'.format(vni_pool))

    if is_show_details:
        pass

