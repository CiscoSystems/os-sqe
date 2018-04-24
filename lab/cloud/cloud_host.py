from lab.server import Server


class CloudHost(Server):

    def __init__(self, cloud, mx_ip, name):
        self.cloud = cloud
        self.mx_ip = mx_ip
        self.name = name
        super(CloudHost, self).__init__(ip=cloud.mediator.ip, username=self.SQE_USERNAME, password=None)

    def __repr__(self):
        return self.name or 'No yet '

    def host_exe(self, cmd):
        cmd = 'ssh -o StrictHostKeyChecking=no root@' + self.name + " '" + cmd + "'"
        return self.exe(cmd=cmd, is_warn_only=True)

    @staticmethod
    def host_list(cloud):
        hosts = cloud.os_cmd(['openstack host list -f json'])[0]
        etc_hosts = {x.split()[1]: x.split()[0] for x in cloud.mediator.exe('cat /etc/hosts').split('\r\n') if 'localhost' not in x}
        control_names = set([x['Host Name'] for x in hosts if x['Service'] == 'scheduler'])
        compute_names = set([x['Host Name'] for x in hosts if x['Service'] == 'compute'])

        assert len(control_names - set(etc_hosts)) == 0 and len(compute_names - set(etc_hosts)) == 0

        controls = [CloudHost(cloud=cloud, mx_ip=etc_hosts[x], name=x) for x in control_names]
        computes = []
        for comp_name in compute_names:
            c = CloudHost(cloud=cloud, mx_ip=etc_hosts[comp_name], name=comp_name)
            computes.append(c)
            a = c.host_exe('compute crudini --get /etc/nova/nova.conf serial_console enabled && compute crudini --get /etc/nova/nova.conf serial_console proxyclient_address')
            if a.split('\r\n')[0] == 'true' and a.split('\r\n')[1] == c.mx_ip:
                continue
            c.host_exe('compute crudini --set /etc/nova/nova.conf serial_console enabled true && compute crudini --set /etc/nova/nova.conf serial_console proxyclient_address {} && systemctl restart docker-novacpu'.format(c.mx_ip))

        return controls, computes
