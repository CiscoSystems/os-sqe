def start(lab, log, args):
    import datetime
    import time
    import random
    from fabric.context_managers import shell_env

    duration = args['duration']
    public_net = args.get('public_net', 'nova')
    flavor_name = args.get('flavor_name', 'm1.nano')
    image_name = args.get('image_name', 'cirros')
    image_user = args.get('image_user', 'cirros')
    image_password = args.get('image_password', 'cubswin:)')

    server = lab.director()

    def run_cmd(cmd, warn_only=False):
        with shell_env(OS_AUTH_URL=lab.cloud.end_point, OS_USERNAME=lab.cloud.user, OS_PASSWORD=lab.cloud.password, OS_TENANT_NAME=lab.cloud.tenant):
            return server.run(cmd, warn_only=warn_only).stdout

    cmd = 'ping -c {time} -w {time} {ip} | while read pong; do echo "$(date +"%s"): $pong"; done > log.txt &'

    net_name = 'net-{0}'.format(random.randint(0, 10000))
    inst_name = 'inst1-{0}'.format(random.randint(0, 10000))

    try:
        image_id = run_cmd("glance image-list | grep '{0}' | awk '{{print $2}}'".format(image_name)).split('\n')[0].strip()

        net_id = run_cmd("neutron net-create {0} | grep '| id' | awk '{{print $4}}'".format(net_name))
        vlan_id = run_cmd("neutron net-show {0} | grep 'provider:segmentation_id' | awk '{{print $4}}'".format(net_id))
        subnet_id = run_cmd("neutron subnet-create {0} 10.10.10.10/24 | grep '| id' | awk '{{print $4}}'".format(net_id))
        port_id = run_cmd("neutron port-create {0} | grep '| id' | awk '{{print $4}}'".format(net_id))
        inst_id = run_cmd("nova boot --flavor {0} --image '{1}' --nic port-id={2} {3} | grep '| id' | awk '{{print $4}}'".format(flavor_name, image_id, port_id, inst_name))

        start_time = time.time()
        inst_status = 'BUILD'
        while not (inst_status == 'ACTIVE'):
            if start_time + 180 < time.time() or not (inst_status == 'BUILD'):
                raise Exception('instances are in {0} state'.format(inst_status))
            inst_status = run_cmd("nova show {0} | grep '| status' | awk '{{print $4}}'".format(inst_id))

        log.info('status=1')
    except Exception as ex:
        print datetime.datetime.now(), ": ", ex
        log.info('status=0')

    try:
        if 'inst_id' in locals():
            run_cmd('nova delete {0}'.format(inst_id), warn_only=True)
        if 'port_id' in locals():
            run_cmd('neutron port-delete {0}'.format(port_id), warn_only=True)
        if 'net_id' in locals():
            run_cmd('neutron net-delete {0}'.format(net_id), warn_only=True)
    except Exception as ex:
        print datetime.datetime.now(), ": ", ex
