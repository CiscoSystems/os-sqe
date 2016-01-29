from fabric.api import task


class Cloud:
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'
    ROLE_MEDIATOR = 'mediator'

    def __init__(self, cloud, user, admin, tenant, password, end_point=None, mediator=None):
        self.name = cloud
        self.user = user
        self.admin = admin
        self.tenant = tenant
        self.password = password
        self.info = {'controller': [], 'ucsm': [], 'network': [], 'compute': []}
        self.service_end_points = {x: {} for x in self.services()}
        self.mac_2_ip = {}
        self.hostname_2_ip = {}
        self.end_point = end_point
        self.mediator = mediator  # special server to be used to execute CLI commands for this cloud

    def __repr__(self):
        return '--os-username {u} --os-tenant-name {t} --os-password {p} --os-auth-url {a}'.format(u=self.user, t=self.tenant, p=self.password, a=self.get_end_point())

    @staticmethod
    def services():
        return ['nova', 'neutron']

    def get_end_point(self):
        return self.end_point or 'http://{0}:5000/v2.0'.format(self.get_first(self.ROLE_CONTROLLER, 'ip'))

    def get(self, role, parameter):
        """
            :param role: controller, network, compute, ucsm
            :param parameter: ip, mac, hostname
            :return: a list of values for given parameter of given role
        """
        return [server.get(parameter) for server in self.info.get(role, [])]

    def get_first(self, role, parameter):
        """
            :param role: controller, network, compute, ucsm
            :param parameter: ip, mac, hostname
            :return: the first value for given parameter of given role
        """
        values = self.get(role=role, parameter=parameter)
        if values:
            return values[0]
        else:
            return 'NoValueFor' + role + parameter

    def add_server(self, config_name, server):
        """ Set all parameters for the given server
        :param config_name:
        :param server:
        """
        if config_name.startswith('aio'):
            role = self.ROLE_CONTROLLER
        else:
            role = None
            for x in self.info.keys():
                if x in config_name:
                    role = x
                    break
            if role is None:
                raise RuntimeError('Failed to deduce cloud role for server {0}'.format(server))

        self.hostname_2_ip[server.hostname] = server.ip
        self.mac_2_ip[server.ip_mac] = server.ip

        _info = {'ip': server.ip, 'mac': server.ip_mac, 'username': server.username, 'hostname': server.hostname, 'password': server.password}
        self.info[role].append(_info)

    def add_service_end_point(self, service, url, end_point):
        self.service_end_points[service].update({url: end_point})

    def get_service_end_point(self, service, url):
        return self.service_end_points[service][url]

    def create_open_rc(self):
        """ Creates open_rc for the given cloud"""
        open_rc = """
export OS_USERNAME={user}
export OS_TENANT_NAME={tenant}
export OS_PASSWORD={password}
export OS_AUTH_URL={end_point}
"""
        return open_rc.format(user=self.user, tenant=self.tenant, password=self.password, end_point=self.get_end_point())

    def log(self):
        from lab.logger import lab_logger

        lab_logger.info('\n\n Report on lab: ')
        for hostname in sorted(self.hostname_2_ip.keys()):
            lab_logger.info(hostname + ': ' + self.hostname_2_ip[hostname])
        lab_logger.info('\n')
        for role in sorted(self.info.keys()):
            lab_logger.info(role + ' ip: ' + ' '.join(self.get(role=role, parameter='ip')))

    def cmd(self, cmd, server=None):
        """Execute a single command versus this cloud
        :param cmd: string with command to be executed
        :param server: optional server on which this command to be executed
        """

        server = server or self.mediator
        return server.run(command='{cmd} {creds}'.format(cmd=cmd, creds=self))

    def list_networks(self):
        output = []

        for net in self._parse_cli_output(self.cmd('openstack network list')):
            net_show = self._parse_cli_output(self.cmd('openstack network show {0}'.format(net['ID'])))
            output += net_show
        return output

    @staticmethod
    def _parse_cli_output(output_lines):
        """Borrowed from tempest-lib. Parse single table from cli output.
        :param output_lines:
        :returns: dict with list of column names in 'headers' key and rows in 'values' key.
        """

        if not isinstance(output_lines, list):
            output_lines = output_lines.split('\n')

        if not output_lines[-1]:
            output_lines = output_lines[:-1]  # skip last line if empty (just newline at the end)

        columns = Cloud._table_columns(output_lines[2])
        is_2_values = len(columns) == 2

        def line_to_row(input_line):
            return [input_line[col[0]:col[1]].strip() for col in columns]

        headers = None
        d2 = {}
        output_list = []
        for line in output_lines[3:-1]:
            row = line_to_row(line)
            if is_2_values:
                d2[row[0]] = row[1]
            else:
                headers = headers or line_to_row(output_lines[1])
                output_list.append({headers[i]: row[i] for i in xrange(len(columns))})

        return output_list if output_list else [d2]

    @staticmethod
    def _table_columns(first_table_row):
        """Borrowed from tempest-lib. Find column ranges in output line.
        :returns: list of tuples (start,end) for each column detected by plus (+) characters in delimiter line.
        """
        positions = []
        start = 1  # there is '+' at 0
        while start < len(first_table_row):
            end = first_table_row.find('+', start)
            if end == -1:
                break
            positions.append((start, end))
            start = end + 1
        return positions


@task
def g10(cmd):
    """fab cloud.g10:'neutron net-list' \t\t Run single command on G10 cloud.
        :param cmd: command to be executed
    """
    from lab.deployers.DeployerExistingOSP7 import DeployerExistingOSP7

    d = DeployerExistingOSP7(config={'cloud': 'g10', 'hardware-lab-config': 'g10'})
    cloud = d.deploy_cloud([])
    cloud.cmd(cmd=cmd)
