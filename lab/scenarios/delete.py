def start(lab, log, args):
    import time

    how_many = args['how_many']
    is_cleanup = args.get('is_cleanup', True)
    unique_partern_in_name = args.get('unique_partern_in_name', 'sqe-test')

    start_time = time.time()
    for i in xrange(0, how_many):
        once(cloud=lab.cloud, name='{0}-{1}'.format(unique_partern_in_name, i), log=log, is_cleanup=is_cleanup)
    log.info('{0} net-subnet-ports created in {1} secs'.format(how_many, time.time()-start_time))
