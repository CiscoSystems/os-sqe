from lab.with_log import WithLogMixIn
from lab.decorators import section


class OS(WithLogMixIn):
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'
    ROLE_MEDIATOR = 'mediator'

    def __init__(self, name, mediator, openrc_path, openrc_body):
        self._provider_physical_network = 'Default Value Set In Cloud.__init__()'

        self._openstackclient_version = None
        self.name = name
        self._openrc_path = openrc_path
        self._os_sqe_password = 'os-sqe'
        self._username,  self._tenant, self._password, self._end_point = self.process_openrc(openrc_as_string=openrc_body)
        self.mediator = mediator    # special server to be used to execute CLI commands for this cloud
        self.pod = mediator.pod     # Instance of class Laboratory (sigleton)
        self._instance_counter = 0  # this counter is used to count how many instances are created via this class
        services_lst = self.os_host_list()
        control_names_in_cloud = set([x['Host Name'] for x in services_lst if x['Service'] == 'scheduler'])
        compute_names_in_cloud = set([x['Host Name'] for x in services_lst if x['Service'] == 'compute'])
        if set([x.id for x in self.computes]) != compute_names_in_cloud:
            raise RuntimeError('computes known by cloud are different from computes known by pod')
        if set([x.id for x in self.controls]) != control_names_in_cloud:
            raise RuntimeError('controls known by cloud are different from ones from pod')

    @property
    def controls(self):
        return self.pod.controls

    @property
    def computes(self):
        return self.pod.computes

    @staticmethod
    def process_openrc(openrc_as_string):
        username, tenant, password, end_point = None, None, None, None
        for line in openrc_as_string.split('\n'):
            if 'OS_USERNAME' in line:
                username = line.split('=')[-1].strip()
            elif 'OS_TENANT_NAME' in line:
                tenant = line.split('=')[-1].strip()
            elif 'OS_PASSWORD' in line:
                password = line.split('=')[-1].strip()
            elif 'OS_AUTH_URL' in line:
                end_point = line.split('=')[-1].strip()
        return username, tenant, password, end_point

    def __repr__(self):
        return 'Cloud {}: {} {} {}'.format(self.name, self._username, self._password, self._end_point)

    @property
    def os_openstackclient_version(self):
        if self._openstackclient_version is None:
            self._openstackclient_version = self.os_cmd(cmd='openstack --version').split(' ')[-1]
        return self._openstackclient_version

    @staticmethod
    def _add_name_prefix(name):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME
        return '{}-{}'.format(UNIQUE_PATTERN_IN_NAME, name)

    def create_open_rc(self):
        """ Creates open_rc for the given cloud"""
        open_rc = """
export OS_USERNAME={user}
export OS_TENANT_NAME={tenant}
export OS_PASSWORD={password}
export OS_AUTH_URL={end_point}
"""
        return open_rc.format(user=self._username, tenant=self._tenant, password=self._password, end_point=self._end_point)

    def os_cmd(self, cmd, comment='', server=None, is_warn_only=False):
        server = server or self.mediator
        cmd = 'source {} && {} {}'.format(self._openrc_path, cmd, '# ' + comment if comment else '')
        ans = server.exe(command=cmd, is_warn_only=is_warn_only)
        if '-f csv' in cmd:
            return self._process_csv_output(ans)
        elif '-f json' in cmd:
            return self._process_json_output(ans)
        elif '-f table' in cmd:
            return self._process_table_output(answer=ans, command=cmd)
        else:
            return self._process_table_output(answer=ans, command=cmd)

    @staticmethod
    def _filter(minus_c, flt):
        return '{c} {g}'.format(c='-c ' + minus_c if minus_c else '', g=' | grep ' + flt if flt else '')

    @staticmethod
    def _process_json_output(answer):
        import json

        try:
            ans = json.loads(answer)
        except ValueError:  # openstack image show non-existing -f json which gives "Could not find resource non-existing"
            try:
                ans = json.loads(answer.split('\r\n')[-1])  # neutron net-create kir1 -f json produces Created a new network:\n [{"Field": "admin_state_up", "Value": true} ....
            except ValueError:
                return {}
        if type(ans) is list and len(ans) and 'Value' in ans[0]:
            return {x['Field']: x['Value'] for x in ans}  # some old OS clients return [{"Field": "foo", "Value": "bar"}, ...]
        else:
            return ans

    @staticmethod
    def _process_csv_output(answer):
        output_list = []
        if answer:
            lines = answer.split('\n')
            keys = []
            for i, line in enumerate(lines):
                line = line.strip('\r')
                if i == 0:  # it's line of keys like: "ID","Name" or "ID","Name","Subnets"
                    keys = map(lambda x: x.strip('" '), line.split(','))
                else:
                    output_list.append(dict(zip(keys, map(lambda x: x.strip('" '), line.split(',')))))
        return output_list

    @staticmethod
    def _process_table_output(command, answer):
        if 'delete' in command or not answer:
            return []
        else:
            lines = answer.split('\r\n')
            if len(lines) == 1:
                return []
            output = []
            keys = [x.strip() for x in lines[1].split('|') if x]
            for line in lines[3:-1]:
                values = [x.strip() for x in line.split('|') if x]
                d = {k: v for k, v in zip(keys, values)}
                output.append(d)
            return output

    @staticmethod
    def _names_from_answer(ans):
        return filter(lambda x: x not in ['name', '|', '+--------+'], ans.split())

    def get_fip_network(self):
        ans = self.os_cmd('neutron net-list --router:external=True -c name')
        net_names = self._names_from_answer(ans)
        if not net_names:
            return '', 'physnet1'
        fip_network = net_names[0]
        ans = self.os_cmd('neutron net-list -c provider:physical_network --name {0}'.format(fip_network))
        physnet = filter(lambda x: x not in ['provider:physical_network', '|', '+---------------------------+'], ans.split())[0]
        return fip_network, physnet

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

        columns = OS._table_columns(output_lines[2])
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
                output_list.append({headers[i]: row[i] for i in range(len(columns))})

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

    def list_ports(self, network_id=None):
        query = ' '.join(['--network-id=' + network_id if network_id else ''])
        return self.os_cmd('neutron port-list -f csv {q}'.format(q=query))

    def show_port(self, port_id):
        return self.os_cmd('neutron port-show {0} -f json'.format(port_id))

    def os_create_fips(self, fip_net, how_many):
        return map(lambda _: self.os_cmd('neutron floatingip-create {0}'.format(fip_net.get_net_name())), range(how_many))

    def os_flavor_list(self):
        return self.os_cmd('openstack flavor list -f json')

    def exe(self, cmd):
        """
        :param cmd: Execute this command on all hosts of the cloud
        :return:
        """
        ans = {}
        # noinspection PyBroadException
        try:
            hosts = self.os_host_list()
            unique_hosts = set([x.get('Host Name', 'see {}:327'.format(__file__)) for x in hosts])
            for host in unique_hosts:
                ans[host] = self.mediator.exe("ssh -o StrictHostKeyChecking=no {} '{}'".format(host, cmd), is_warn_only=True)
        except:
            ans['This cloud is not active'] = ''
        return ans

    def os_host_list(self):
        return self.os_cmd('openstack host list -f json')

    @section('Creating key pair', estimated_time=5)
    def os_keypair_create(self):
        from lab import with_config
        with open(with_config.KEY_PUBLIC_PATH) as f:
            public_path = self.mediator.r_put_string_as_file_in_dir(string_to_put=f.read(), file_name='sqe_public_key')

        self.os_cmd('openstack keypair create {} --public-key {}'.format(self._add_name_prefix('key1'), public_path))

    def os_keypair_delete(self, keypairs):
        map(lambda x: self.os_cmd('openstack keypair delete {}'.format(x['Name'])), keypairs)

    def os_keypair_list(self):
        return self.os_cmd('openstack keypair list -f json')

    def os_port_create(self, server_number, net_name, ip, mac, sriov=False):
        sriov_addon = '--binding:vnic-type direct' if sriov else ''
        fixed_ip_addon = '--fixed-ip ip_address={ip} --mac-address {mac}'.format(ip=ip, mac=mac) if ip else ''
        port_name = self._add_name_prefix('{}-port-{}-on-{}'.format(server_number, 'sriov' if sriov else 'virio', net_name))
        return self.os_cmd('neutron port-create -f json --name {port_name} {net_name} {ip_addon} {sriov_addon}'.format(port_name=port_name, net_name=net_name, ip_addon=fixed_ip_addon, sriov_addon=sriov_addon))

    def os_port_delete(self, ports):
        map(lambda x: self.os_cmd(cmd='neutron port-delete ' + x['id'], comment=x['name']), ports)

    def os_port_list(self):
        return self.os_cmd('neutron port-list -f json')

    def os_server_create(self, srv_name, flavor_name, image_name, zone_name, port_ids):
        ports_part = ' '.join(map(lambda x: '--nic port-id=' + x, port_ids))
        return self.os_cmd('openstack server create {} --flavor {} --image "{}" --availability-zone nova:{} --security-group default --key-name sqe-key1 {} -f json'.format(srv_name, flavor_name, image_name, zone_name, ports_part))

    def os_server_show(self, name_or_id):
        return self.os_cmd('openstack server show -f json {}'.format(name_or_id))

    def os_security_group_list(self):
        return self.os_cmd('openstack security group list -f json')

    def os_security_group_delete(self, security_groups):
        map(lambda x: self.os_cmd('openstack security group delete {}'.format(x['ID'])), security_groups)

    def os_security_group_rule_delete(self, rules):
        map(lambda x: self.os_cmd('openstack security group rule delete {}'.format(x['ID'])), rules)

    def os_security_group_rule_list(self, security_group):
        return self.os_cmd('openstack security group rule list -f json {}'.format(security_group['ID']))

    def os_server_group_list(self):
        return self.os_cmd(cmd='nova server-group-list')

    def os_server_group_delete(self, server_groups):
        if len(server_groups):
            ids = [s['Id'] for s in server_groups]
            names = [s['Name'] for s in server_groups]
            self.os_cmd('nova server-group-delete ' + ' '.join(ids), comment=' '.join(names))

    def os_user_list(self):
        return self.os_cmd('openstack user list -f json')

    def os_user_create(self, user_name):
        return self.os_cmd('openstack user create --password {} {} -f json'.format(self._os_sqe_password, user_name))

    def os_user_delete(self, users):
        map(lambda x: self.os_cmd('openstack user delete {}'.format(x['ID']), comment=x['Name']), users)

    def os_cleanup(self, is_all=False):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME
        from lab.cloud.cloud_server import CloudServer
        from lab.cloud.cloud_image import CloudImage
        from lab.cloud.cloud_router import CloudRouter
        from lab.cloud.cloud_network import CloudNetwork
        from lab.cloud.cloud_flavor import CloudFlavor

        CloudServer.cleanup(cloud=self, is_all=is_all)

        ports = self.os_port_list()
        keypairs = self.os_keypair_list()
        server_groups = self.os_server_group_list()
        security_groups = [x for x in self.os_security_group_list() if x['Name'] != 'default']  # don not delete default security group
        users = [x for x in self.os_user_list() if x['Name'] not in ['admin', 'glance', 'neutron', 'cinder', 'nova', 'cloudpulse']]

        if not is_all:
            ports = filter(lambda p: UNIQUE_PATTERN_IN_NAME in p['name'], ports)
            keypairs = filter(lambda k: UNIQUE_PATTERN_IN_NAME in k['Name'], keypairs)
            server_groups = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], server_groups)
            security_groups = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], security_groups)
            users = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], users)

        CloudRouter.cleanup(cloud=self, is_all=is_all)
        self.os_port_delete(ports=ports)
        CloudNetwork.cleanup(cloud=self, is_all=is_all)
        self.os_keypair_delete(keypairs=keypairs)
        CloudImage.cleanup(cloud=self, is_all=is_all)
        CloudFlavor.cleanup(cloud=self, is_all=is_all)
        self.os_security_group_delete(security_groups=security_groups)
        self.os_server_group_delete(server_groups=server_groups)
        self.os_user_delete(users=users)

        for sec_grp in self.os_security_group_list():  # delete all non IP rules from all default security groups
            if sec_grp['Name'] != 'default':
                continue
            rules = self.os_security_group_rule_list(security_group=sec_grp)
            self.os_security_group_rule_delete(rules=[x for x in rules if x['IP Protocol']])

    def r_collect_information(self, regex, comment):
        body = ''
        for cmd in [self._form_log_grep_cmd(log_files='/var/log/*', regex=regex), 'neutronserver grep ^mechanism_driver /etc/neutron/plugins/ml2/ml2_conf.ini',
                    'neutronserver grep -A 5 "\[ml2_cc\]" /etc/neutron/plugins/ml2/ml2_conf.ini']:
            for host, text in self.exe(cmd).items():
                body += self._format_single_cmd_output(cmd=cmd, ans=text, node=host)

        addon = '_' + '_'.join(comment.split()) if comment else ''
        self.log_to_artifact(name='cloud_{}{}.txt'.format(self.name, addon), body=body)
        return body

    def os_quota_set(self):
        admin_id = [x['ID'] for x in self.os_project_list() if x['Name'] == 'admin'][0]
        self.os_cmd('openstack quota set --instances 1000 --cores 2000 --ram 512000 --networks 100 --subnets 300 --ports 500 {}'.format(admin_id))

    def os_project_list(self):
        return self.os_cmd(cmd='openstack project list -f json')
