def start(context, log, args):
    import paramiko
    from paramiko.ssh_exception import SSHException
    import re
    import socket
    import time

    name = args.get('name', 'UCSM')
    duration = args['duration']
    period = args['period']

    states = {'UP': 1, 'DOWN': 0, 'UNRESPONSIVE': -1}
    ucsm_timeout = 5

    ucsm_ip, ucsm_user, ucsm_password = context.ucsm_creds()
    # Possible to specify credentials in arguments
    ucsm_ip = args.get('ip', ucsm_ip)
    ucsm_user = args.get('user', ucsm_user)
    ucsm_password = args.get('password', ucsm_password)

    client = None
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()

    def ucsm_connect():
        client.connect(ucsm_ip, username=ucsm_user, password=ucsm_password, timeout=ucsm_timeout)

    def ucsm_exec(cmd):
        try:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=ucsm_timeout)
        except (SSHException, AttributeError) as ex:
            if 'SSH session not active' in ex.message \
                    or 'Timeout openning channel' in ex.message \
                    or "has no attribute 'open_session'" in ex.message:
                # Try to reconnect if session is not active
                ucsm_connect()
                stdin, stdout, stderr = client.exec_command(cmd, timeout=ucsm_timeout)
        return ''.join(stdout.readlines())

    def parse_state(raw_state):
        # Ex: 'B: UP, PRIMARY'
        res = re.match('^(A|B):\s+(\w+),\s+(\w+)', raw_state)
        return res.group(1), res.group(2), res.group(3)

    start_time = time.time()
    while start_time + duration > time.time():
        try:
            res = ucsm_exec('show cluster state')
            cluster_state = res.split('\n\n')

            # Parse output
            ha_ready = int('HA READY' in res)
            raw_state1, raw_state2 = cluster_state[1].split('\n')

            fi1_name, fi1_state, fi1_role = parse_state(raw_state1)
            fi2_name, fi2_state, fi2_role = parse_state(raw_state2)

            msg = 'ucsm_name={n} cluster_state={ha} state_{fi1n}={fi1s} role_{fi1n}={fi1r} state_{fi2n}={fi2s} role_b={fi1r} exception=0'.format(
                n=name, ha=ha_ready, fi1n=fi1_name, fi1s=states[fi1_state], fi1r=fi1_role, fi2n=fi2_name, fi2s=states[fi2_state], fi2r=fi2_role)
            log.info(msg)
        except (SSHException, socket.timeout, IndexError) as ex:
            log.info('ucsm_name={n} exception=1'.format(n=name))
        time.sleep(period)
