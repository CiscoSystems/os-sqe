def test(iteration, log):
    from fabric.api import local, settings
    import datetime
    import re

    id = lambda result: re.search('id\s+\|\s+([-\w]+)', ''.join(res.stdout)).group(1)

    name = 'test_net_{0}'.format(str(iteration))
    net_id = None
    subnet_id = None
    port_id = None
    try:
        log.info("######### Start time: " + str(datetime.datetime.now()))
        res = local('neutron net-create {0}'.format(name), capture=True)
        net_id = id(res)
        res = local('neutron subnet-create {0} 10.0.100.0/24'.format(net_id), capture=True)
        subnet_id = id(res)
        res = local('neutron port-create {0}'.format(net_id), capture=True)
        port_id = id(res)
        local('neutron port-delete {0}'.format(port_id))
        local('neutron subnet-delete {0}'.format(subnet_id))
        local('neutron net-delete {0}'.format(net_id))
        log.info("######### End time: " + str(datetime.datetime.now()))
    except:
        with settings(warn_only=False):
            if port_id:
                local('neutron port-delete {0}'.format(port_id))
            if net_id:
                local('neutron net-delete {0}'.format(net_id))


def main(context, log, args):
    for id in xrange(0, args['times']):
        test(id, log)

