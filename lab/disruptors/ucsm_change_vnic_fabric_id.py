def start(context, log, args):
    """
        Changes "Fabric ID" property of a vNIC. For example it is set to a-b then it will be changed to b-a.
        If explicitly set fabric_id attribute the value will be set to desired by you.
    """
    import yaml
    from fabric.api import settings, run

    service_profile = args['service_profile']
    vnics = [v.strip() for v in args.get('vnics', 'eth0,eth1').split(',')]
    fabric_id = args.get('fabric_id')

    ucsm_ip, ucsm_user, ucsm_password = context.ucsm_creds()

    show_cmd = 'scope org ; scope service-profile {0} ; scope vnic {1} ; show detail | no-more'
    set_cmd = 'scope org ; scope service-profile {0} ; scope vnic {1} ; set fabric {2} ; commit-buffer'

    with settings(host_string='{user}@{ip}'.format(user=ucsm_user, ip=ucsm_ip), password=ucsm_password, connection_attempts=1, timeout=30, warn_only=True):
        for vnic in vnics:
            if not fabric_id:
                res = run(show_cmd.format(service_profile, vnic), shell=False)
                details = yaml.load(res.stdout)
                cur_fabric_id = details['vNIC']['Fabric ID']
                # reverse current fabric id value
                id1, id2 = cur_fabric_id.lower().split()
                new_fabric_id = '{0}-{1}'.format(id2, id1)
            else:
                new_fabric_id = fabric_id
            res = run(set_cmd.format(service_profile, vnic, new_fabric_id), shell=False)
            log.info('service_profile={0} vnic={1} fabric_id={2} result={3}'.format(service_profile, vnic, new_fabric_id, res.return_code))

