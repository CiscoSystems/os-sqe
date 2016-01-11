def start(lab, log, args):
    import time

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
    log.info('status=all_deleted in time={0} secs'.format(time.time()-start_time))
