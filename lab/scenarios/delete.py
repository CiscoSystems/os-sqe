def start(lab, log, args):
    import time
    from lab.nodes import n9k
    from lab.nodes import fi

    unique_pattern_in_name = args.get('unique_pattern_in_name', 'sqe-test')
    server = lab.controllers()[0]

    start_time = time.time()
    for ob_type in ['port', 'net']:
        res = server.run(command='neutron {o}-list {l} | grep {u} | awk \'{{print $2}}\''.format(o=ob_type, l=lab.cloud, u=unique_pattern_in_name)).split('\n')
        i = len(res)
        for oid in res:
            if oid:
                res = server.run(command='neutron {ob}-delete {id} {lab_creds}'.format(ob=ob_type, id=oid.strip(),
                                                                                       lab_creds=lab.cloud), warn_only=True)
                # Sometimes neutron timeouts, rerun the command if so
                if not res:
                    time.sleep(60)
                    server.run(command='neutron {ob}-delete {id} {lab_creds}'.format(ob=ob_type, id=oid.strip(), lab_creds=lab.cloud), warn_only=True)
                log.info("n_{0}s={1} status=deleted".format(ob_type, i))
                i -= 1
    ucsm_ip, ucsm_username, ucsm_password = lab.ucsm_creds()
    fi = fi.FI(ucsm_ip, ucsm_username, ucsm_password)
    fi.delete_vlans('OS-')
    n9k_ip1, n9k_ip2, n9k_username, n9k__password = lab.n9k_creds()
    nx1 = n9k.Nexus(n9k_ip1, n9k_username, n9k__password)
    nx2 = n9k.Nexus(n9k_ip1, n9k_username, n9k__password)
    nx1.no_vlans('q-')
    nx2.no_vlans('q-')

    log.info('status=all_deleted in time={0} secs'.format(time.time()-start_time))
