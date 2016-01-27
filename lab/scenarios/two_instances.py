def start(lab, log, args):
    import datetime
    import time
    import random
    from fabric.context_managers import shell_env
    import paramiko
    import re

    time_to_ping = args['time_to_ping']
    public_net = args.get('public_net', 'nova')
    flavor_name = args.get('flavor_name', 'm1.nano')
    image_name = args.get('image_name', 'cirros')
    image_user = args.get('image_user', 'cirros')
    image_password = args.get('image_password', 'cubswin:)')

    server = lab.director()

    def run_cmd(cmd):
        with shell_env(OS_AUTH_URL=lab.cloud.end_point, OS_USERNAME=lab.cloud.user, OS_PASSWORD=lab.cloud.password, OS_TENANT_NAME=lab.cloud.tenant):
            return server.run(cmd).stdout

    def inst_run_cmd(ip, cmd, user=image_user, password=image_password):
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.load_system_host_keys()
        res = None
        for i in range(12):
            try:
                client.connect(ip, username=user, password=password, timeout=60)
                stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
                res = ''.join(stdout.readlines()).strip()
                client.close()
            except Exception as ex:
                time.sleep(10)
                if i == 11:
                    raise ex
        return res

    cmd = 'ping -c {time} -w {time} {ip} | while read pong; do echo "$(date +"%s"): $pong"; done > log.txt &'

    net_name = 'net-{0}'.format(random.randint(0, 10000))
    router_name = 'router-{0}'.format(random.randint(0, 10000))
    inst1_name = 'inst1-{0}'.format(random.randint(0, 10000))
    inst2_name = 'inst2-{0}'.format(random.randint(0, 10000))

    try:
        image_id = run_cmd("glance image-list | grep '{0}' | awk '{{print $2}}'".format(image_name)).split('\n')[0].strip()

        net_id = run_cmd("neutron net-create {0} | grep '| id' | awk '{{print $4}}'".format(net_name))
        subnet_id = run_cmd("neutron subnet-create {0} 10.10.10.10/24 | grep '| id' | awk '{{print $4}}'".format(net_id))
        router_id = run_cmd("neutron router-create {0} | grep '| id' | awk '{{print $4}}'".format(router_name))
        run_cmd('neutron router-gateway-set {0} {1}'.format(router_id, public_net))
        run_cmd('neutron router-interface-add {0} {1}'.format(router_id, subnet_id))
        port1_id = run_cmd("neutron port-create {0} | grep '| id' | awk '{{print $4}}'".format(net_id))
        port2_id = run_cmd("neutron port-create {0} | grep '| id' | awk '{{print $4}}'".format(net_id))
        inst1_id = run_cmd("nova boot --flavor {0} --image '{1}' --nic port-id={2} {3} | grep '| id' | awk '{{print $4}}'".format(flavor_name, image_id, port1_id, inst1_name))
        inst2_id = run_cmd("nova boot --flavor {0} --image '{1}' --nic port-id={2} {3} | grep '| id' | awk '{{print $4}}'".format(flavor_name, image_id, port2_id, inst2_name))

        start_time = time.time()
        inst1_status = ''
        inst2_status = ''
        while not(inst1_status == 'ACTIVE' and inst2_status == 'ACTIVE'):
            inst1_status = run_cmd("nova show {0} | grep '| status' | awk '{{print $4}}'".format(inst1_id))
            inst2_status = run_cmd("nova show {0} | grep '| status' | awk '{{print $4}}'".format(inst2_id))
            if start_time + 60 < time.time():
                raise Exception('instances are in {0} {1} states'.format(inst1_status, inst2_status))

        fip1 = run_cmd("neutron floatingip-create nova | grep '| id' | awk '{{print $4}}'")
        fip2 = run_cmd("neutron floatingip-create nova | grep '| id' | awk '{{print $4}}'")
        run_cmd("neutron floatingip-associate {0} {1}".format(fip1, port1_id))
        run_cmd("neutron floatingip-associate {0} {1}".format(fip2, port2_id))

        fip1_ip = run_cmd("neutron floatingip-show {0} | grep 'floating_ip_address' | awk '{{print $4}}'".format(fip1))
        fip2_ip = run_cmd("neutron floatingip-show {0} | grep 'floating_ip_address' | awk '{{print $4}}'".format(fip2))

        fixed_ip1 = run_cmd("neutron floatingip-show {0} | grep 'fixed_ip_address' | awk '{{print $4}}'".format(fip1))
        fixed_ip2 = run_cmd("neutron floatingip-show {0} | grep 'fixed_ip_address' | awk '{{print $4}}'".format(fip2))

        inst_run_cmd(fip1_ip, cmd.format(time=time_to_ping, ip=fixed_ip2))
        inst_run_cmd(fip2_ip, cmd.format(time=time_to_ping, ip=fixed_ip1))

        time.sleep(time_to_ping + 10)
        res1 = inst_run_cmd(fip1_ip, 'cat log.txt')
        res2 = inst_run_cmd(fip2_ip, 'cat log.txt')

        date1 = datetime.datetime.fromtimestamp(int(inst_run_cmd(fip1_ip, 'date +"%s"')))
        date2 = datetime.datetime.fromtimestamp(int(inst_run_cmd(fip2_ip, 'date +"%s"')))

        timedelta1 = date1 - datetime.datetime.now()
        timedelta2 = date2 - datetime.datetime.now()

        for src, dest, srvout in [('srv1', 'srv2', res1), ('srv2', 'srv1', res2)]:
            lines = srvout.split('\n')
            for line in lines:
                r = re.match('(\d+): 64 bytes from (\d+\.\d+\.\d+\.\d+): seq=\d+ ttl=\d+ time=(\d+\.\d+) ms', line)
                if r:
                    dt_seconds = int(r.group(1)) - timedelta1.seconds if src == 'srv1' else int(r.group(1)) - timedelta2.seconds
                    dt = datetime.datetime.fromtimestamp(dt_seconds)
                    ip = r.group(2)
                    res = r.group(3)
                    log.info('@timestamp={0}, src={1}, dest={2}, dest_ip={3}, result={4}'.format(dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"), src, dest, ip, res))
    except Exception as ex:
        print ex

    try:
        run_cmd('neutron floatingip-disassociate {0}'.format(fip1))
        run_cmd('neutron floatingip-disassociate {0}'.format(fip2))
        if 'inst1_id' in locals():
            run_cmd('nova delete {0}'.format(inst1_id))
        if 'inst2_id' in locals():
            run_cmd('nova delete {0}'.format(inst2_id))
        if 'port1_id' in locals():
            run_cmd('neutron port-delete {0}'.format(port1_id))
        if 'port2_id' in locals():
            run_cmd('neutron port-delete {0}'.format(port2_id))
        if 'router_id' in locals():
            run_cmd('neutron router-interface-delete {0} {1}'.format(router_id, subnet_id))
            run_cmd('neutron router-gateway-clear {0}'.format(router_id))
            run_cmd('neutron router-delete {0}'.format(router_id))
        if 'net_id' in locals():
            run_cmd('neutron net-delete {0}'.format(net_id))
    except Exception as ex:
        print ex
