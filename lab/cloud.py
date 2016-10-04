from lab.with_log import WithLogMixIn


class Cloud(WithLogMixIn):
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'
    ROLE_MEDIATOR = 'mediator'

    def __init__(self, cloud, user, admin, tenant, password, end_point=None, mediator=None):
        self._show_subnet_cmd = 'neutron subnet-show -f shell '

        self._fip_network = 'Default Value Set In Cloud.__init__()'
        self._provider_physical_network = 'Default Value Set In Cloud.__init__()'
        self._openstack_version = 'Default Value Set In Cloud.__init__()'

        self._name = cloud
        self._user = user
        self._admin = admin
        self._tenant = tenant
        self._password = password
        self.info = {'controller': [], 'ucsm': [], 'network': [], 'compute': []}
        self.service_end_points = {x: {} for x in self.services()}
        self.mac_2_ip = {}
        self.hostname_2_ip = {}
        self.end_point = end_point
        self.mediator = mediator  # special server to be used to execute CLI commands for this cloud
        self._dns = '171.70.168.183'
        self._unique_pattern_in_name = 'sqe-test'
        self._instance_counter = 0  # this counter is used to count how many instances are created via this class
        self._image = {'url': 'http://172.29.173.233/fedora/fedora-dnsmasq-localadmin-ubuntu.qcow2', 'method': 'sha256sum', 'checksum': '06da8e3efb68bd29e1d8957f3ebb8678bd731fe4c68a8af9ef437c6846cd2bb9'}

    def __repr__(self):
        return 'Cloud {n}: {a} {u} {p}'.format(u=self._user, n=self._name, p=self._password, a=self.get_end_point())

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

    def get_name(self):
        return self._name

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
        return open_rc.format(user=self._user, tenant=self._tenant, password=self._password, end_point=self.get_end_point())

    def os_cmd(self, cmd, server=None, is_warn_only=False):
        server = server or self.mediator
        ans = server.exe(command='{cmd} --os-username {u} --os-tenant-name {t} --os-password {p} --os-auth-url {a}'.format(cmd=cmd, u=self._user, t=self._tenant, p=self._password, a=self.get_end_point()), is_warn_only=is_warn_only)
        if '-f csv' in cmd:
            return self._process_csv_output(ans)
        elif '-f json' in cmd:
            return self._process_json_output(ans)
        elif '-f shell' in cmd:
            return self._process_shell_output(ans)
        else:
            return ans

    @staticmethod
    def _filter(minus_c, flt):
        return '{c} {g}'.format(c='-c ' + minus_c if minus_c else '', g=' | grep ' + flt if flt else '')

    @staticmethod
    def _process_json_output(answer):
        import json

        lst = json.loads(answer.split('\n')[-1])  # neutron returns Created a new port:\r\n[{"Field": "admin_state_up", "Value": true}.... while openstack returns just serialized array
        if not lst or 'Value' not in lst[0]:  # [{"ID": "foo", "Name": "bar"}, ...] for list operation
            return lst
        else:
            d = {}
            for x in lst:  # [{"Field": "foo", "Value": "bar"}, ...] for other operations
                d[x['Field']] = x['Value']
            return d

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
    def _process_shell_output(answer):
        output_dict = {}
        if answer:
            lines = answer.split('\n')
            for line in lines:
                if '=' not in line:  # might be lines not in form a=b
                    continue
                line = line.strip('\r')
                key, value = line.split('=', 1)
                output_dict[key.strip('" ')] = value.strip('" ')
        return output_dict

    @staticmethod
    def _names_from_answer(ans):
        return filter(lambda x: x not in ['name', '|', '+--------+'], ans.split())

    def get_fip_network(self):
        if not self._fip_network:
            ans = self.os_cmd('neutron net-list --router:external=True -c name')
            net_names = self._names_from_answer(ans)
            if not net_names:
                return
            self._fip_network = net_names[0]
            ans = self.os_cmd('neutron net-list -c provider:physical_network --name {0}'.format(self._fip_network))
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

    @staticmethod
    def get_cidrs4(class_a, how_many):
        from netaddr import IPNetwork

        return map(lambda number: IPNetwork('{a}.{b}.{c}.0/24'.format(a=class_a, b=number / 256, c=number % 256)), range(1, how_many+1))

    def get_net_names(self, common_part_of_name, how_many):
        return map(lambda number: '{sqe_pref}-{name}-net-{number}'.format(sqe_pref=self._unique_pattern_in_name, name=common_part_of_name, number=number), range(1, how_many+1))

    def get_net_subnet_lines(self, common_part_of_name, class_a, how_many, vlan=None, is_dhcp=True):
        net_names = self.get_net_names(common_part_of_name=common_part_of_name, how_many=how_many)
        subnet_names = map(lambda x: x.replace('-net-', '-subnet-'), net_names)
        cidrs = self.get_cidrs4(class_a=class_a, how_many=how_many)
        net_vs_subnet = {}
        for i in range(len(net_names)):
            phys_net_addon = '--provider:physical_network={phys_net} --provider:network_type=vlan --provider:segmentation_id={vlan}'.format(phys_net=self._provider_physical_network, vlan=vlan+i) if vlan else ''

            net_line = 'openstack network create {name} {addon} -f shell'.format(name=net_names[i], addon=phys_net_addon)
            cidr, gw, start, stop = cidrs[i], cidrs[i][1], cidrs[i][10], cidrs[i][200]
            sub_line = 'neutron subnet-create {n_n} {cidr} --name {s_n} --gateway {gw} --dns-nameserver {dns} {dhcp} --allocation-pool start={ip1},end={ip2} -f shell'.format(n_n=net_names[i],
                                                                                                                                                                              s_n=subnet_names[i],
                                                                                                                                                                              cidr=cidr, gw=gw, dns=self._dns,
                                                                                                                                                                              dhcp='' if is_dhcp else '--disable-dhcp',
                                                                                                                                                                              ip1=start, ip2=stop)
            net_vs_subnet[net_line] = sub_line
        return net_vs_subnet

    def create_router(self, number, on_nets):
        router_name = self._unique_pattern_in_name + '-router-' + str(number)
        self.os_cmd('neutron router-create ' + router_name)
        for subnet_name in sorted(on_nets.values()):
            self.os_cmd('neutron router-interface-add {router} {subnet}'.format(router=router_name, subnet=subnet_name))
        self.os_cmd('neutron router-gateway-set {router} {net}'.format(router=router_name, net=self._fip_network))

    def list_ports(self, network_id=None):
        query = ' '.join(['--network-id=' + network_id if network_id else ''])
        return self.os_cmd('neutron port-list -f csv {q}'.format(q=query))

    def show_port(self, port_id):
        return self.os_cmd('neutron port-show {0} -f shell'.format(port_id))

    def list_networks(self):
        networks = self.os_cmd('neutron net-list -f csv')
        for network in networks:
            network.update(self.os_cmd('neutron net-show {id} -f shell'.format(id=network.get('id'))))
        return networks

    def _calculate_static_ip_and_mac(self, allocation_pool):
        a = map(lambda x: int(x), allocation_pool[0].split('.'))
        a[-1] += self._instance_counter
        ip = '.'.join(map(lambda x: str(x), a))
        mac = '00:10:' + ':'.join(map(lambda x: '{0:02}'.format(x) if x < 100 else '{0:02x}'.format(x), a))
        return ip, mac

    def create_fips(self, how_many):
        fips = map(lambda _: self.os_cmd('neutron floatingip-create {0}'.format(self._fip_network)), range(how_many))
        return fips

    def server_reboot(self, name, hard=False):
        flags = ['--hard' if hard else '--soft']
        self.os_cmd('openstack server reboot {flags} {name}'.format(flags=' '.join(flags), name=name))
        self.wait_instances_ready(names=[name])

    def server_rebuild(self, name, image):
        self.os_cmd('openstack server rebuild {name} --image {image}'.format(name=name, image=image))
        self.wait_instances_ready(names=[name])

    def server_suspend(self, name):
        self.os_cmd('openstack server suspend {name}'.format(name=name))
        self.wait_instances_ready(names=[name], status='SUSPENDED')

    def server_resume(self, name):
        self.os_cmd('openstack server resume {name}'.format(name=name))
        self.wait_instances_ready(names=[name])

    def wait_instances_ready(self, names=None, status='ACTIVE'):
        import time

        while True:
            all_instances = self.os_server_list()
            our_instances = filter(lambda x: x['Name'] in names, all_instances) if names else all_instances
            instances_in_error = filter(lambda x: x['Status'] == 'ERROR', our_instances)
            instances_in_active = filter(lambda x: x['Status'] == status, our_instances)
            if len(instances_in_active) == len(names):
                return
            if instances_in_error:
                for instance in instances_in_error:
                    self.analyse_instance_problems(instance)
                raise RuntimeError('These instances failed: {0}'.format(instances_in_error))
            time.sleep(30)

    def analyse_instance_problems(self, instance):
        from lab.server import Server

        instance_details = self.os_server_show(instance['Name'])
        compute_node = Server(ip=instance_details['os-ext-srv-attr:host'], username='root', password='cisco123')
        compute_node.exe(command='grep {instance_id} | grep -i error'.format(instance_id=instance_details['id']))

    def r_collect_information(self, regex, comment):
        try:
            hosts = self.os_host_list()
            body = ''
            for host in sorted(hosts):
                for cmd in [self._form_log_grep_cmd(log_files='/var/log/*', regex=regex)]:
                    ans = self.mediator.exe('ssh -o StrictHostKeyChecking=no {} {}'.format(host, cmd), is_warn_only=True)
                    body += self._format_single_cmd_output(cmd=cmd, ans=ans, node=host)
        except:
            body = 'This cloud is not active'

        addon = '_' + '_'.join(comment.split()) if comment else ''
        self.log_to_artifact(name='cloud_{}{}.txt'.format(self._name, addon), body=body)
        return body

    def os_host_list(self):
        return set([x.get('Host Name') for x in self.os_cmd('openstack host list -f json')])

    def os_image_create(self):
        name = self._unique_pattern_in_name + '-fedora'
        if not filter(lambda image: image['Name'] == name, self.os_image_list()):
            image_path = self.mediator.r_get_remote_file(url=self._image['url'], to_directory='cloud_images', checksum=self._image['checksum'], method=self._image['method'])
            self.os_cmd('openstack image create {name} --public --protected --disk-format qcow2 --container-format bare --file {path}'.format(name=name, path=image_path))
            self.log('image={} status=requested'.format(name))
        return self.os_image_wait(name)

    def os_image_analyse_problem(self, image):
        self.r_collect_information(regex=image['Name'], comment='image problem')
        raise RuntimeError('image {} failed'.format(image['name']))

    def os_image_delete(self, name):
        return self.os_cmd('openstack image delete {}'.format(name))

    def os_image_list(self):
        return self.os_cmd('openstack image list -f json')

    def os_image_show(self, name):
        return self.os_cmd('openstack image show -f json {}'.format(name))

    def os_image_wait(self, name):
        import time

        while True:
            image = self.os_cmd('openstack image show -f json {}'.format(name))
            if image['status'] == 'ERROR':
                self.os_image_analyse_problem(image)
            elif image['status'] == 'active':
                self.log('image={} status=active'.format(name))
                return image
            time.sleep(15)

    def os_keypair_create(self):
        from lab import with_config
        with open(with_config.KEY_PUBLIC_PATH) as f:
            public_path = self.mediator.r_put_string_as_file_in_dir(string_to_put=f.read(), file_name='sqe_public_key')

        self.os_cmd('openstack keypair create {sqe_pref}-key1 --public-key {public}'.format(sqe_pref=self._unique_pattern_in_name, public=public_path))

    def os_keypair_delete(self, name):
        return self.os_cmd('openstack keypair delete {}'.format(name))

    def os_keypair_list(self):
        return self.os_cmd('openstack keypair list -f json')

    def os_network_create(self, common_part_of_name, class_a, how_many, vlan=None, is_dhcp=True):
        net_vs_subnet_names = {}
        for net_line, subnet_line in sorted(self.get_net_subnet_lines(common_part_of_name=common_part_of_name, class_a=class_a, how_many=how_many, vlan=vlan, is_dhcp=is_dhcp).items()):
            network = self.os_cmd(net_line)
            subnet = self.os_cmd(subnet_line)
            net_vs_subnet_names[network['name']] = {'network': network, 'subnet': subnet}
        return net_vs_subnet_names

    def os_network_delete(self, name):
        return self.os_cmd('openstack network delete {}'.format(name))

    def os_network_list(self):
        return self.os_cmd('openstack network list -f json')

    def os_port_create(self, server_name, on_nets, is_fixed_ip=False, sriov=False):
        import re

        pids = []
        sriov_addon = '--binding:vnic-type direct' if sriov else ''

        for net_name, desc in sorted(on_nets.items()):
            if is_fixed_ip:
                ip, mac = self._calculate_static_ip_and_mac(re.findall(r'[0-9]+(?:\.[0-9]+){3}', desc['subnet']['allocation_pools']))
                fixed_ip_addon = '--fixed-ip ip_address={ip} --mac-address {mac}'.format(ip=ip, mac=mac)
            else:
                fixed_ip_addon = ''

            port_name = '{sqe_pref}-{server_name}-port-{sriov}-on-{net_name}'.format(sqe_pref=self._unique_pattern_in_name, server_name=server_name, sriov='sriov' if sriov else 'virio', net_name=net_name)
            port = self.os_cmd('neutron port-create -f json --name {port_name} {net_name} {ip_addon} {sriov_addon}'.format(port_name=port_name, net_name=net_name, ip_addon=fixed_ip_addon, sriov_addon=sriov_addon))
            pids.append(port['id'])
        return pids

    def os_port_delete(self, name):
        return self.os_cmd('neutron port-delete {}'.format(name))

    def os_port_list(self):
        return self.os_cmd('neutron port-list -f json')

    def os_router_list(self):
        return self.os_cmd('neutron router-list -f json')

    def os_server_create(self, name, flavor, image_name, on_ports):
        ports_part = ' '.join(map(lambda x: '--nic port-id=' + x, on_ports))
        server_name = '{sqe_pref}-{name}'.format(sqe_pref=self._unique_pattern_in_name, name=name)
        self.os_cmd('openstack server create {name} --flavor {flavor} --image "{image}" --security-group default --key-name sqe-test-key1 {ports_part}'.format(name=server_name, flavor=flavor, image=image_name, ports_part=ports_part))
        self.wait_instances_ready(names=[server_name])
        self._instance_counter += 1
        return server_name

    def os_server_delete(self, name):
        return self.os_cmd('openstack server delete {}'.format(name))

    def os_server_list(self):
        return self.os_cmd('openstack server list -f json')

    def os_server_show(self, name):
        return self.os_cmd('openstack server show -f json {}'.format(name))

    def os_cleanup(self):
        servers = self.os_server_list()
        routers = self.os_router_list()
        ports = self.os_port_list()
        keypairs = self.os_keypair_list()
        networks = self.os_network_list()

        sqe_servers = filter(lambda x: self._unique_pattern_in_name in x['Name'], servers)
        sqe_ports = filter(lambda x: self._unique_pattern_in_name in x['name'], ports)
        sqe_networks = filter(lambda x: self._unique_pattern_in_name in x['Name'], networks)
        sqe_routes = filter(lambda x: self._unique_pattern_in_name in x['name'], routers)
        sqe_keypairs = filter(lambda x: self._unique_pattern_in_name in x['Name'], keypairs)

        map(lambda server: self.os_server_delete(server['Name']), sqe_servers)
        map(lambda router: self._clean_router(router['name']), sqe_routes)
        map(lambda port: self.os_port_delete(port['name']), sqe_ports)
        map(lambda net: self.os_network_delete(net['Name']), sqe_networks)
        map(lambda keypair: self.os_keypair_delete(keypair['Name']), sqe_keypairs)

    def _clean_router(self, router_name):
        import re

        self.os_cmd('neutron router-gateway-clear {0}'.format(router_name))
        ans = self.os_cmd('neutron router-port-list {0} | grep -v HA'.format(router_name))
        subnet_ids = re.findall('"subnet_id": "(.*)",', ans)
        map(lambda subnet_id: self.os_cmd('neutron router-interface-delete {router_name} {subnet_id}'.format(router_name=router_name, subnet_id=subnet_id)), subnet_ids)
        self.os_cmd('neutron router-delete {0}'.format(router_name))

    def verify_cloud(self):
        ans = self.os_cmd('openstack --version')
        self._openstack_version = int(''.join(ans.rsplit('.')).replace('openstack ', ''))

        self.os_network_list()
        self.os_port_list()
        self.os_router_list()
        self.os_server_list()
        self.get_fip_network()

        # for service in self.services():
        #     for url in ['publicURL', 'internalURL', 'adminURL']:
        #         end_point = self.cmd('openstack catalog show {service} | grep {url} | awk \'{{print $4}}\''.format(service=service, url=url))
        #         self.add_service_end_point(service=service, url=url, end_point=end_point)

        self.os_cmd('neutron quota-update --network 100 --subnet 100 --port 500')
        return self

    @staticmethod
    def from_openrc(name, mediator, openrc_as_string):
        user = tenant = password = end_point = None
        for line in openrc_as_string.split('\n'):
            if 'OS_USERNAME' in line:
                user = line.split('=')[-1].strip()
            elif 'OS_TENANT_NAME' in line:
                tenant = line.split('=')[-1].strip()
            elif 'OS_PASSWORD' in line:
                password = line.split('=')[-1].strip()
            elif 'OS_AUTH_URL' in line:
                end_point = line.split('=')[-1].strip()

        return Cloud(cloud=name, user=user, tenant=tenant, admin=tenant, password=password, end_point=end_point, mediator=mediator)
