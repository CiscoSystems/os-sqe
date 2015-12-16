def test(iteration, log, is_cleanup):
    from fabric.api import local, settings
    import re

    id = lambda result: re.search('id\s+\|\s+([-\w]+)', ''.join(res.stdout)).group(1)

    name = 'test_net_{0}'.format(str(iteration))
    net_id = None
    subnet_id = None
    port_id = None
    try:
        res = local('neutron net-create {0}'.format(name), capture=True)
        net_id = id(res)
        res = local('neutron subnet-create {0} 10.0.100.0/24'.format(net_id), capture=True)
        subnet_id = id(res)
        res = local('neutron port-create --name={0} {1}'.format(name, net_id), capture=True)
        port_id = id(res)
        if is_cleanup:
            local('neutron port-delete {0}'.format(port_id))
            local('neutron subnet-delete {0}'.format(subnet_id))
            local('neutron net-delete {0}'.format(net_id))
        log.info('{0} net-subnet-port created'.format(iteration))
    except:
        with settings(warn_only=False):
            if port_id:
                local('neutron port-delete {0}'.format(port_id))
            if net_id:
                local('neutron net-delete {0}'.format(net_id))


def start(context, log, args):
    import time

    start_time = time.time()
    for i in xrange(0, args['times']):
        test(iteration=i, log=log, is_cleanup=args.get('cleanup', True))
    log.info('{0} net-subnet-ports created in {1} secs'.format(args['times'], time.time()-start_time))
