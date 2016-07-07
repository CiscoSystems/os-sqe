import sys


class Cloud:
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'
    ROLE_MEDIATOR = 'mediator'

    def __init__(self, cloud, user, password, tenant, end_point=None):
        self._openstack_bin = 'openstack'
        self._neutron_bin = 'neutron'

        self._create_server_cmd = self._openstack_bin + ' server create -f shell '
        self._create_subnet_cmd = self._neutron_bin + ' subnet-create -f shell '
        self._create_network_cmd = self._openstack_bin + ' network create -f shell '
        self._create_port_cmd = self._neutron_bin + ' port-create -f shell '

        self._delete_server_cmd = self._openstack_bin + ' server delete '
        self._delete_keypair_cmd = self._openstack_bin + ' keypair delete '
        self._delete_network_cmd = self._openstack_bin + ' network delete '
        self._delete_subnet_cmd = self._neutron_bin + ' subnet-delete '
        self._delete_port_cmd = self._neutron_bin + ' port-delete '

        self._show_server_cmd = self._openstack_bin + ' server show -f shell '
        self._show_subnet_cmd = self._neutron_bin + ' subnet-show -f shell '
        
        self._list_network_cmd = self._openstack_bin + ' network list -f json'
        self._list_subnet_cmd = self._openstack_bin + ' subnet list -f json'
        self._list_router_cmd = self._openstack_bin + ' router list -f json'
        self._list_port_cmd = self._openstack_bin + ' port list -f json'
        self._list_server_cmd = self._openstack_bin + ' server list -f json'
        self._list_keypair_cmd = self._openstack_bin + ' keypair list -f json'
        self._list_image_cmd = self._openstack_bin + ' image list -f json'

        self._fip_network = 'Default Value Set In Cloud.__init__()'
        self._provider_physical_network = 'Default Value Set In Cloud.__init__()'
        self._openstack_version = 'Default Value Set In Cloud.__init__()'

        self.name = cloud
        self.user = user
        self.tenant = tenant
        self.password = password
        self.info = {'controller': [], 'ucsm': [], 'network': [], 'compute': []}
        self.mac_2_ip = {}
        self.hostname_2_ip = {}
        self.end_point = end_point
        self._dns = '171.70.168.183'
        self._unique_pattern_in_name = 'sqe-test'
        self._instance_counter = 0  # this counter is used to count how many instances are created via this class



    def __repr__(self):
        return '--os-username {u} --os-tenant-name {t} --os-password {p} --os-auth-url {a}'.format(u=self.user, t=self.tenant, p=self.password, a=self.get_end_point())

    def get_end_point(self):
        return self.end_point

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

    def cmd(self, cmd):
        import json
        import subprocess
        import sys

        venv = '. ' + sys.prefix + '/bin/activate && ' if hasattr(sys, 'real_prefix') else ''
        ans = subprocess.check_output('{venv}{cmd} {creds}'.format(venv=venv, cmd=cmd, creds=self), shell=True)

        sys.stdout.writelines(str(ans))
        if '-f csv' in cmd:
            return self._process_csv_output(ans)
        elif '-f json' in cmd:
            return json.loads(ans)
        elif '-f shell' in cmd:
            return self._process_shell_output(ans)
        else:
            return ans

    @staticmethod
    def _filter(minus_c, flt):
        return '{c} {g}'.format(c='-c ' + minus_c if minus_c else '', g=' | grep ' + flt if flt else '')

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
            ans = self.cmd(self._neutron_bin + ' net-list --router:external=True -c name')
            net_names = self._names_from_answer(ans)
            if not net_names:
                return
            self._fip_network = net_names[0]
            ans = self.cmd(self._neutron_bin + ' net-list -c provider:physical_network --name {0}'.format(self._fip_network))
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

    def get_net_subnet_lines(self, common_part_of_name, class_a, how_many, vlan=None, is_dhcp=True):
        net_names = self.get_net_names(common_part_of_name=common_part_of_name, how_many=how_many)
        subnet_names = map(lambda x: x.replace('-net-', '-subnet-'), net_names)
        cidrs = self.get_cidrs4(class_a=class_a, how_many=how_many)
        net_vs_subnet = {}
        for i in xrange(len(net_names)):
            phys_net_addon = '--provider:physical_network={phys_net} --provider:network_type=vlan --provider:segmentation_id={vlan}'.format(phys_net=self._provider_physical_network, vlan=vlan+i) if vlan else ''

            net_line = self._openstack_bin + ' network create {name} {addon} -f shell'.format(name=net_names[i], addon=phys_net_addon)
            cidr, gw, start, stop = cidrs[i], cidrs[i][1], cidrs[i][10], cidrs[i][200]
            sub_line = self._neutron_bin + ' subnet-create {n_n} {cidr} --name {s_n} --gateway {gw} --dns-nameserver {dns} {dhcp} --allocation-pool start={ip1},end={ip2} -f shell'.format(n_n=net_names[i],
                                                                                                                                                                              s_n=subnet_names[i],
                                                                                                                                                                              cidr=cidr, gw=gw, dns=self._dns,
                                                                                                                                                                              dhcp='' if is_dhcp else '--disable-dhcp',
                                                                                                                                                                              ip1=start, ip2=stop)
            net_vs_subnet[net_line] = sub_line
        return net_vs_subnet

    def create_net_subnet(self, common_part_of_name, class_a, how_many, vlan=None, is_dhcp=True):
        net_vs_subnet_names = {}
        for net_line, subnet_line in sorted(self.get_net_subnet_lines(common_part_of_name=common_part_of_name, class_a=class_a, how_many=how_many, vlan=vlan, is_dhcp=is_dhcp).iteritems()):
            network = self.cmd(net_line)
            subnet = self.cmd(subnet_line)
            net_vs_subnet_names[network['name']] = {'network': network, 'subnet': subnet}
        return net_vs_subnet_names

    def create_router(self, number, on_nets):
        router_name = self._unique_pattern_in_name + '-router-' + str(number)
        self.cmd(self._neutron_bin + ' router-create ' + router_name)
        for subnet_name in sorted(on_nets.values()):
            self.cmd(self._neutron_bin + ' router-interface-add {router} {subnet}'.format(router=router_name, subnet=subnet_name))
        self.cmd(self._neutron_bin + ' router-gateway-set {router} {net}'.format(router=router_name, net=self._fip_network))

    def create_ports(self, instance_name, on_nets, is_fixed_ip=False, sriov=False):
        import re

        ports = []
        sriov_addon = '--binding:vnic-type direct' if sriov else ''

        for net_name, desc in sorted(on_nets.items()):
            if is_fixed_ip:
                ip, mac = self._calculate_static_ip_and_mac(re.findall(r'[0-9]+(?:\.[0-9]+){3}', desc['subnet']['allocation_pools']))
                fixed_ip_addon = '--fixed-ip ip_address={ip} --mac-address {mac}'.format(ip=ip, mac=mac)
            else:
                fixed_ip_addon = ''

            port_name = '{sqe_pref}-{instance_name}-port-{sriov}-on-{net_name}'.format(sqe_pref=self._unique_pattern_in_name, instance_name=instance_name, sriov='sriov' if sriov else 'virio', net_name=net_name)
            port = self.cmd(self._create_port_cmd + ' --name {port_name} {net_name}  {ip_addon} {sriov_addon}'.format(port_name=port_name, net_name=net_name, ip_addon=fixed_ip_addon, sriov_addon=sriov_addon))
            ports.append(port)
        return ports

    def list_ports(self, network_id=None):
        query = ' '.join(['--network-id=' + network_id if network_id else ''])
        return self.cmd(self._neutron_bin + ' port-list -f csv {q}'.format(q=query))

    def show_port(self, port_id):
        return self.cmd(self._neutron_bin + ' port-show {0} -f shell'.format(port_id))

    def list_networks(self):
        networks = self.cmd(self._neutron_bin + ' net-list -f csv')
        for network in networks:
            network.update(self.cmd(self._neutron_bin + ' net-show {id} -f shell'.format(id=network['id'])))
        return networks

    def show_net(self, net_id):
        return self.cmd(self._neutron_bin + ' net-show {0} -f shell'.format(net_id))

    def show_subnet(self, subnet_id):
        return self.cmd(self._neutron_bin + ' subnet-show {0} -f shell'.format(subnet_id))

    def server_list(self):
        return self.cmd(self._list_server_cmd)

    def _calculate_static_ip_and_mac(self, allocation_pool):
        a = map(lambda x: int(x), allocation_pool[0].split('.'))
        a[-1] += self._instance_counter
        ip = '.'.join(map(lambda x: str(x), a))
        mac = '00:10:' + ':'.join(map(lambda x: '{0:02}'.format(x) if x < 100 else '{0:02x}'.format(x), a))
        return ip, mac

    def create_fips(self, how_many):
        fips = map(lambda _: self.cmd(self._neutron_bin + ' floatingip-create {0}'.format(self._fip_network)), xrange(how_many))
        return fips

    def create_key_pair(self):
        self._keypair_name = '{sqe_pref}-key1'.format(sqe_pref=self._unique_pattern_in_name)
        self._keypair = self.cmd(self._openstack_bin + ' keypair create {keypair}'.format(keypair=self._keypair_name))

    def create_instance(self, name, flavor, image, on_ports, wait_for_ready=True):
        if image not in self.cmd(self._openstack_bin + ' image list'):
            raise ValueError('Image {0} is not known by cloud'.format(image))
        ports_part = ' '.join(map(lambda x: '--nic port-id=' + x['id'], on_ports))
        instance_name = '{sqe_pref}-{name}'.format(sqe_pref=self._unique_pattern_in_name, name=name)
        instance = self.cmd(self._openstack_bin + ' server create {name} --flavor {flavor} --image "{image}" --security-group default '
                                                  '--key-name {keypair} {ports_part} -f shell'.format(name=instance_name, flavor=flavor,
                                                                                             image=image, ports_part=ports_part,
                                                                                             keypair=self._keypair_name))
        instance_status = None
        if wait_for_ready:
            instance_status = self.wait_instances_ready(names=[instance_name])
        self._instance_counter += 1
        return instance, instance_status

    def server_reboot(self, name, hard=False):
        flags = ['--hard' if hard else '--soft']
        self.cmd(self._openstack_bin + ' server reboot {flags} {name}'.format(flags=' '.join(flags), name=name))
        self.wait_instances_ready(names=[name])

    def server_rebuild(self, name, image):
        self.cmd(self._openstack_bin + ' server rebuild {name} --image {image}'.format(name=name, image=image))
        self.wait_instances_ready(names=[name])

    def server_suspend(self, name):
        self.cmd(self._openstack_bin + ' server suspend {name}'.format(name=name))
        self.wait_instances_ready(names=[name], status='SUSPENDED')

    def server_resume(self, name):
        self.cmd(self._openstack_bin + ' server resume {name}'.format(name=name))
        self.wait_instances_ready(names=[name])

    def wait_instances_ready(self, names=None, status='ACTIVE', timeout=60 * 2):
        import time
        import datetime

        our_instances = None
        start_time = datetime.datetime.now()
        while (datetime.datetime.now() - start_time).seconds < timeout:
            all_instances = self.cmd(self._list_server_cmd)
            our_instances = filter(lambda x: x['Name'] in names, all_instances) if names else all_instances
            instances_in_error = filter(lambda x: x['Status'] == 'ERROR', our_instances)
            instances_in_active = filter(lambda x: x['Status'] == status, our_instances)
            if len(instances_in_active) == len(names):
                sys.stdout.writelines(str(our_instances))
                return True
            if instances_in_error:
                sys.stdout.writelines(str(our_instances))
                return False
            time.sleep(30)
        sys.stdout.writelines(str(our_instances))
        return False

    def create_image(self, name, url):
        if not filter(lambda image: image['Name'] == name, self.cmd(self._list_image_cmd)):
            image_path = self.mediator.wget_file(url=url, to_directory='cloud_images')
            self.cmd(self._openstack_bin + ' image create {name} --public --protected --disk-format qcow2 --container-format bare --file {path}'.format(name=name, path=image_path))
        return name

    def cleanup(self):
        servers = self.cmd(self._list_server_cmd)
        routers = self.cmd(self._list_router_cmd)
        ports = self.cmd(self._list_port_cmd)
        keypairs = self.cmd(self._list_keypair_cmd)
        networks = self.cmd(self._list_network_cmd)

        sqe_servers = filter(lambda x: self._unique_pattern_in_name in x['Name'], servers)
        sqe_ports = filter(lambda x: self._unique_pattern_in_name in x['Name'], ports)
        sqe_networks = filter(lambda x: self._unique_pattern_in_name in x['Name'], networks)
        sqe_routes = filter(lambda x: self._unique_pattern_in_name in x['name'], routers)
        sqe_keypairs = filter(lambda x: self._unique_pattern_in_name in x['Name'], keypairs)

        map(lambda server: self.cmd(self._delete_server_cmd + server['ID']), sqe_servers)
        map(lambda router: self._clean_router(router['ID']), sqe_routes)
        map(lambda port: self.cmd(self._delete_port_cmd + port['ID']), sqe_ports)
        map(lambda net: self.cmd(self._delete_network_cmd + net['ID']), sqe_networks)
        map(lambda keypair: self.cmd(self._delete_keypair_cmd + keypair['Name']), sqe_keypairs)

    def _clean_router(self, router_name):
        import re

        self.cmd(self._neutron_bin + ' router-gateway-clear {0}'.format(router_name))
        ans = self.cmd(self._neutron_bin + ' router-port-list {0} | grep -v HA'.format(router_name))
        subnet_ids = re.findall('"subnet_id": "(.*)",', ans)
        map(lambda subnet_id: self.cmd(self._neutron_bin + ' router-interface-delete {router_name} {subnet_id}'.format(router_name=router_name, subnet_id=subnet_id)), subnet_ids)
        self.cmd(self._neutron_bin + ' router-delete {0}'.format(router_name))

    def verify_cloud(self):
        ans = self.cmd(self._openstack_bin + ' --version')
        self._openstack_version = int(''.join(ans.rsplit('.')).replace(self._openstack_bin + ' ', ''))
        
        self._list_network_cmd = self._openstack_bin + ' network list -f ' + ('json' if self._openstack_version > 200 else 'csv')
        self._list_port_cmd = self._openstack_bin + ' port list -f json' if self._openstack_version > 200 else self._neutron_bin + ' port-list -f csv'
        self._list_router_cmd = self._openstack_bin + ' router list -f json' if self._openstack_version > 200 else self._neutron_bin + ' router-list -f csv'
        self._list_server_cmd = self._openstack_bin + ' server list -f ' + ('json' if self._openstack_version > 200 else 'csv')
        self._list_keypair_cmd = self._openstack_bin + ' keypair list -f ' + ('json' if self._openstack_version > 200 else 'csv')
        self._list_image_cmd = self._openstack_bin + ' image list -f ' + ('json' if self._openstack_version > 200 else 'csv')

        self.cmd(self._list_network_cmd)
        self.cmd(self._list_port_cmd)
        self.cmd(self._list_router_cmd)
        self.cmd(self._list_server_cmd)
        self.get_fip_network()

        # for service in self.services():
        #     for url in ['publicURL', 'internalURL', 'adminURL']:
        #         end_point = self.cmd(self._openstack_bin + ' catalog show {service} | grep {url} | awk \'{{print $4}}\''.format(service=service, url=url))
        #         self.add_service_end_point(service=service, url=url, end_point=end_point)

        self.cmd(self._neutron_bin + ' quota-update --network 100 --subnet 100 --port 500')
        return self
