def start(context, log, args):
    import os
    import yaml
    from fabric.api import run, settings

    # PRIMARY or SUBORDINATE
    role = args.get('role', 'PRIMARY')

    ip, user, password = context.ucsm_creds()

    def call_ucsm(command):
        with settings(host_string='{user}@{ip}'.format(user=user, ip=ip), password=password, connection_attempts=1, warn_only=False, timeout=1):
            try:
                return run(command, shell=False, quiet=True).stdout
            except:
                return ''

    fabric_id = call_ucsm('show cluster state | include {0}'.format(role))[0].strip(':').lower()
    fabric_ip = yaml.load(call_ucsm("show fabric-interconnect {0} detail | egrep 'OOB IP Addr:'".format(fabric_id)))['OOB IP Addr']

    script = """#!/usr/bin/expect
set user {user}
set pass {password}
set switch_ip {ip}

spawn ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ${{user}}@${{switch_ip}}
expect "Password:" {{send "$pass\r"}}

expect "#" {{send "connect local-mgmt\r"}}
expect "(local-mgmt)#" {{send "reboot\r"}}
expect "(yes/no):" {{send "yes\r"}}
sleep 5
exit
""".format(ip=fabric_ip, user=user, password=password)
    script_name = 'ucsm_reload.exp'

    director = context.director()
    script_path = os.path.join(director.temp_dir, script_name)

    director.put_string_as_file_in_dir(script, script_path, '/')
    director.exe('yum install -y expect')
    res = director.exe('expect {0}'.format(script_path), warn_only=True)
    log.info('result={0}'.format(res.return_code))
