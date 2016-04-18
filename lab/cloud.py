class Cloud:
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'
    ROLE_MEDIATOR = 'mediator'

    def __init__(self, cloud, user, admin, tenant, password, end_point=None, mediator=None):
        import re

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
        self._dns = '171.70.168.183'
        self._unique_pattern_in_name = 'sqe-test'
        self._re_sqe = re.compile('(sqe-test-.*) ')
        self._fip_network = None
        self._provider_physical_network = None

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

    def cmd(self, cmd, server=None, is_warn_only=False):
        server = server or self.mediator
        parts = cmd.split('|')  # handler command like neutron net-list | grep foo
        flt = '|'.join(parts[1:])
        return server.run(command='{cmd} {creds} {flt}'.format(cmd=parts[0], creds=self, flt='|' + flt if flt else ''), warn_only=is_warn_only)

    @staticmethod
    def _filter(minus_c, flt):
        return '{c} {g}'.format(c='-c ' + minus_c if minus_c else '', g=' | grep ' + flt if flt else '')

    def list_networks(self, minus_c=None, flt=None):
        output = []

        for net in self._parse_cli_output(self.cmd('openstack network list' + self._filter(minus_c=minus_c, flt=flt))):
            net_show = self._parse_cli_output(self.cmd('openstack network show {0}'.format(net['ID'])))
            output += net_show
        return output

    def list_ports(self):
        output = []

        for port in self._parse_cli_output(self.cmd('openstack port list')):
            port_show = self._parse_cli_output(self.cmd('openstack port show {0}'.format(port['ID'])))
            output += port_show
        return output

    @staticmethod
    def _names_from_answer(ans):
        return filter(lambda x: x not in ['name', '|', '+--------+'], ans.split())

    def get_fip_network(self):
        if not self._fip_network:
            ans = self.cmd('neutron net-list --router:external=True -c name')
            net_names = self._names_from_answer(ans)
            self._fip_network = net_names[0]
            ans = self.cmd('neutron net-list -c provider:physical_network --name {0}'.format(self._fip_network))
            self._provider_physical_network = filter(lambda x: x not in ['provider:physical_network', '|', '+---------------------------+'], ans.split())[0]
        return self._fip_network

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

    @staticmethod
    def get_cidrs4(class_a, how_many):
        from netaddr import IPNetwork

        return map(lambda number: IPNetwork('{a}.{b}.{c}.0/24'.format(a=class_a, b=number / 256, c=number % 256)), xrange(1, how_many+1))

    def get_net_names(self, common_part_of_name, how_many):
        return map(lambda number: '{sqe_pref}-{name}-net-{number}'.format(sqe_pref=self._unique_pattern_in_name, name=common_part_of_name, number=number), xrange(1, how_many+1))

    def get_net_subnet_lines(self, common_part_of_name, class_a, how_many, vlan=None):
        net_names = self.get_net_names(common_part_of_name=common_part_of_name, how_many=how_many)
        subnet_names = map(lambda x: x.replace('-net-', '-subnet-'), net_names)
        cidrs = self.get_cidrs4(class_a=class_a, how_many=how_many)
        net_vs_subnet = {}
        for i in xrange(len(net_names)):
            phys_net_addon = '--provider:physical_network={phys_net} --provider:network_type=vlan --provider:segmentation_id={vlan}'.format(phys_net=self._provider_physical_network, vlan=vlan+i) if vlan else ''

            net_line = 'neutron net-create {name} {addon} -c name'.format(name=net_names[i], addon=phys_net_addon)
            cidr, gw, start, stop = cidrs[i], cidrs[i][1], cidrs[i][10], cidrs[i][200]
            sub_line = 'neutron subnet-create {n_n} {cidr} --name {s_n} --gateway {gw} --dns-nameserver {dns} --allocation-pool start={ip1},end={ip2} -c name'.format(n_n=net_names[i],
                                                                                                                                                                      s_n=subnet_names[i],
                                                                                                                                                                      cidr=cidr, gw=gw, dns=self._dns,
                                                                                                                                                                      ip1=start, ip2=stop)
            net_vs_subnet[net_line] = sub_line
        return net_vs_subnet

    def create_net_subnet(self, common_part_of_name, class_a, how_many, vlan=None):
        net_vs_subnet_names = {}
        for net_line, subnet_line in sorted(self.get_net_subnet_lines(common_part_of_name=common_part_of_name, class_a=class_a, how_many=how_many, vlan=vlan).iteritems()):
            ans = self.cmd(net_line)
            net_name = self._re_sqe.findall(ans)[0]
            ans = self.cmd(subnet_line)
            subnet_name = self._re_sqe.findall(ans)[0]
            net_vs_subnet_names[net_name] = subnet_name
        return net_vs_subnet_names

    def create_router(self, number, on_nets):
        router_name = self._unique_pattern_in_name + '-router-' + str(number)
        self.cmd('neutron router-create ' + router_name)
        for subnet_name in sorted(on_nets.values()):
            self.cmd('neutron router-interface-add {router} {subnet}'.format(router=router_name, subnet=subnet_name))
        self.cmd('neutron router-gateway-set {router} {net}'.format(router=router_name, net=self._fip_network))

    def create_ports(self, instance_name, on_nets, sriov=False):
        pids = []
        sriov_addon = '--binding:vnic-type direct' if sriov else ''
        for net_name in sorted(on_nets.keys()):
            port_name = '{sqe_pref}-{instance_name}-port-{sriov}-on-{net_name}'.format(sqe_pref=self._unique_pattern_in_name, instance_name=instance_name, sriov='sriov' if sriov else 'virio', net_name=net_name)
            ans = self.cmd('neutron port-create --name {port_name} {net_name} {sriov_addon} -c id '.format(port_name=port_name, net_name=net_name, sriov_addon=sriov_addon))
            pids.append(self._names_from_answer(ans)[9])
        return pids

    def create_fips(self, how_many):
        fips = map(lambda _: self.cmd('neutron floatingip-create {0}'.format(self._fip_network)), xrange(how_many))
        return fips

    def create_key_pair(self):
        from lab import with_config
        with open(with_config.KEY_PUBLIC_PATH) as f:
            public_path = self.mediator.put_string_as_file_in_dir(string_to_put=f.read(), file_name='sqe_public_key')

        self.cmd('openstack keypair create {sqe_pref}-key1 --public-key {public}'.format(sqe_pref=self._unique_pattern_in_name, public=public_path))

    def create_instance(self, name, flavor, image, on_ports):
        if image not in self.cmd('openstack image list'):
            raise ValueError('Image {0} is not known by cloud'.format(image))
        ports_part = ' '.join(map(lambda x: '--nic port-id=' + x, on_ports))
        instance_name = '{sqe_pref}-{name}'.format(sqe_pref=self._unique_pattern_in_name, name=name)
        self.cmd('openstack server create {name} --flavor {flavor} --image "{image}" --security-group default --key-name sqe-test-key1 {ports_part}'.format(name=instance_name, flavor=flavor, image=image, ports_part=ports_part))
        return instance_name

    def create_image(self, url):
        image_path = self.mediator.wget_file(url)
        name = image_path.split('/')[-1]
        self.cmd('glance image-create --architecture i386 --protected=False --name {name} --visibility public --disk-format qcow2 --progress --file {path}  --container-format bare'.format(name=name, path=image_path))
        return image_path

    def cleanup(self):
        import json

        ans = self.cmd(cmd='neutron router-list -c name | grep {sqe_pref}'.format(sqe_pref=self._unique_pattern_in_name), is_warn_only=True)
        router_names = self._names_from_answer(ans)
        ans = self.cmd(cmd='neutron port-list -c name | grep {sqe_pref}'.format(sqe_pref=self._unique_pattern_in_name), is_warn_only=True)
        port_names = self._names_from_answer(ans)
        ans = self.cmd(cmd='neutron net-list -c name | grep {sqe_pref}'.format(sqe_pref=self._unique_pattern_in_name), is_warn_only=True)
        net_names = self._names_from_answer(ans)

        map(lambda router_name: self._clean_router(router_name), sorted(router_names))
        map(lambda port_name: self.cmd('neutron port-delete {0}'.format(port_name)), sorted(port_names))
        map(lambda net_name: self.cmd('openstack network delete {0}'.format(net_name)), sorted(net_names))

        keypairs = json.loads(self.cmd('openstack keypair list -f json'))
        map(lambda keypair: self.cmd('openstack keypair delete {0}'.format(keypair['Name'])), filter(lambda x: self._unique_pattern_in_name in x['Name'], keypairs))

    def _clean_router(self, router_name):
        import re

        self.cmd('neutron router-gateway-clear {0}'.format(router_name))
        ans = self.cmd('neutron router-port-list {0} | grep -v HA'.format(router_name))
        subnet_ids = re.findall('"subnet_id": "(.*)",', ans)
        map(lambda subnet_id: self.cmd('neutron router-interface-delete {router_name} {subnet_id}'.format(router_name=router_name, subnet_id=subnet_id)), subnet_ids)
        self.cmd('neutron router-delete {0}'.format(router_name))

    def verify_cloud(self):
        self.cmd('neutron net-list -c name')
        self.cmd('neutron port-list -c name')
        self.cmd('neutron router-list -c name')
        self.cmd('openstack server list')
        self.get_fip_network()
        for service in self.services():
            for url in ['publicURL', 'internalURL', 'adminURL']:
                end_point = self.cmd('openstack catalog show {service} | grep {url} | awk \'{{print $4}}\''.format(service=service, url=url))
                self.add_service_end_point(service=service, url=url, end_point=end_point)
        self.cmd('neutron quota-update --network 100 --subnet 100 --port 500')
        return self

    @staticmethod
    def from_openrc(name, mediator, openrc_as_string):
        user = tenant = password = end_point = None
        for line in openrc_as_string.split('\n'):
            if 'OS_USERNAME' in line:
                user = line.split('=')[-1].strip()
            if 'OS_TENANT_NAME' in line:
                tenant = line.split('=')[-1].strip()
            if 'OS_PASSWORD' in line:
                password = line.split('=')[-1].strip()
            if 'OS_AUTH_URL' in line:
                end_point = line.split('=')[-1].strip()

        return Cloud(cloud=name, user=user, tenant=tenant, admin=tenant, password=password, end_point=end_point, mediator=mediator)
