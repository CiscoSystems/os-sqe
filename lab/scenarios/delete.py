def start(lab, log, args):
    import time

    unique_pattern_in_name = args.get('unique_pattern_in_name', 'sqe-test')
    server = lab.controllers()[0]

    start_time = time.time()
    for ob_type in ['port', 'net']:
        for oid in server.run(command='neutron {o}-list {l} | grep {u} | awk \'{{print $2}}\''.format(o=ob_type, l=lab.cloud, u=unique_pattern_in_name)).split('\n'):
            if oid:
                server.run(command='neutron {ob}-delete {id} {lab_creds}'.format(ob=ob_type, id=oid.strip(), lab_creds=lab.cloud))
    log.info('All net-subnet-ports deleted in {0} secs'.format(time.time()-start_time))
