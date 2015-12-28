def once(command, log):

    net_id = command('neutron net-create')
    command('neutron subnet-create {net_id} 10.0.100.0/24'.format(net_id=net_id))
    command('neutron port-create {net_id}'.format(net_id=net_id))
    log.info('net-subnet-port created')


def start(lab, log, args):
    import time
    import re

    how_many = args['how_many']
    unique_pattern_in_name = args.get('unique_pattern_in_name', 'sqe-test')

    server = lab.controllers()[0]

    def command(cmd):
        name_part = '{0}-{1}'.format(unique_pattern_in_name, i)
        if 'subnet-create' in cmd:  # subnet-create needs to be before net-create since net-create is a substring of subnet-create
            name_part = '--name ' + name_part + '-subnet'
        elif 'net-create' in cmd:
            name_part += '-net'
        elif 'port-create' in cmd:
            name_part = '--name ' + name_part + '-port'

        res = server.run(command='{cmd} {name_part} {lab_creds}'.format(cmd=cmd, name_part=name_part, lab_creds=lab.cloud))
        if res:
            return re.search('id\s+\|\s+([-\w]+)', ''.join(res.stdout)).group(1)

    start_time = time.time()
    for i in xrange(0, how_many):
        once(command=command, log=log)
    log.info('{0} net-subnet-ports created in {1} secs'.format(how_many, time.time()-start_time))
