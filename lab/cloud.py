from lab.with_log import WithLogMixIn
from lab.decorators import section
from lab.server import Server


UNIQUE_PATTERN_IN_NAME = 'sqe'


class CloudNetwork(object):
    def __init__(self, common_part_of_name, class_a, number, vlan_id, is_dhcp, cloud):
        from netaddr import IPNetwork

        self._net_name = '{}-{}-net-{}'.format(UNIQUE_PATTERN_IN_NAME, common_part_of_name, number)
        self._subnet_name = self._net_name.replace('-net-', '-subnet-')

        self._dns = '171.70.168.183'
        self._vlan_id = vlan_id + number if vlan_id else False
        self._is_dhcp = is_dhcp
        self._network = IPNetwork('{}.{}.0.0/16'.format(class_a, number))

        phys_net_addon = '--provider:physical_network=physnet1 --provider:network_type=vlan --provider:segmentation_id={}'.format(self._vlan_id) if self._vlan_id else ''
        self._net_cmd = 'neutron net-create {} {} -f shell'.format(self._net_name, phys_net_addon)
        cidr, gw, start, stop = self._network, self._network[-2], self._network[1], self._network[5000]
        self._subnet_cmd = 'neutron subnet-create {} {} --name {} --gateway {} --dns-nameserver {} {} --allocation-pool start={},end={} -f shell'.format(self._net_name, cidr, self._subnet_name, gw, self._dns,
                                                                                                                                                         '' if is_dhcp else '--disable-dhcp', start, stop)
        self._net_status, self._subnet_status = cloud.os_network_create(self)

    def get_net_id(self):
        return self._net_status['id']

    def get_segmentation_id(self):
        return self._net_status['provider:segmentation_id']

    def get_net_name(self):
        return self._net_name

    def get_subnet_name(self):
        return self._subnet_name

    def get_net_cmd(self):
        return self._net_cmd

    def get_subnet_cmd(self):
        return self._subnet_cmd

    @staticmethod
    def create(how_many, common_part_of_name, cloud, class_a='99', vlan_id=0, is_dhcp=False):
        return map(lambda n: CloudNetwork(common_part_of_name=common_part_of_name, class_a=class_a, number=n, vlan_id=vlan_id, is_dhcp=is_dhcp, cloud=cloud), range(1, how_many+1))


class CloudServer(Server):

    def __init__(self, number, flavor_name, image, zone_name, on_nets, cloud):
        self._number = number
        self._on_nets = on_nets
        self._ports = []

        ip = None
        for net in on_nets:
            ip = net.get_ip(self._number)
            mac = '00:10:' + ':'.join(map(lambda n: '{0:02}'.format(int(n)) if int(n) < 100 else '{0:02x}'.format(int(x)), str(ip).split('.')))
            self._ports.append(cloud.os_port_create(net_name=net.get_net_name(), ip=ip, mac=mac))
        super(CloudServer, self).__init__(ip=ip, username=image.get_username(), password=image.get_password())
        self._status = cloud.os_server_create(srv_name=self.get_name(), flavor_name=flavor_name, image_name=image.get_name(), zone_name=zone_name, port_ids=[x['id'] for x in self._ports])
        assert self._status['OS-EXT-SRV-ATTR:host'] == zone_name

    def get_name(self):
        return UNIQUE_PATTERN_IN_NAME + '-' + str(self._number)

    @staticmethod
    def create(how_many, flavor_name, image, on_nets, timeout, cloud):

        servers = []
        compute_hosts = cloud.get_compute_hosts()
        for n, comp_n in [(y, 1 + y % len(compute_hosts)) for y in range(how_many)]:  # distribute servers per compute host in round robin
            servers.append(CloudServer(number=n, flavor_name=flavor_name, image=image, on_nets=on_nets, zone_name=compute_hosts[comp_n].get_name(), cloud=cloud))
        cloud.wait_instances_ready(names=[x.get_name() for x in servers], timeout=timeout)


class CloudImage(object):
    def __init__(self, name, url, cloud):

        local_path, checksum, self._username, self._password = cloud.get_mediator().r_get_remote_file(url=url, to_directory='/var/tmp/cloud_images')

        self._status = cloud.os_image_show(name)

        if not self._status or self._status['checksum'] != checksum:
            cloud.os_cmd('openstack image create {} --public --disk-format qcow2 --container-format bare --file {}'.format(name, local_path))
            self._status = cloud.os_image_wait(name)
        else:
            cloud.log('image has a matched checksum: {}'.format(checksum))

    def get_username(self):
        return self._username

    def get_password(self):
        return self._username

    def get_name(self):
        return self._status['Name']

    @staticmethod
    @section('Creating custom image')
    def add_image(image_name, cloud):
        images = {'sqe-iperf': 'http://172.29.173.233/fedora/fedora-dnsmasq-localadmin-ubuntu.qcow2',
                  'FOR_CSR':   'http://172.29.173.233/cloud-images/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2',
                  'testpmd': 'http://172.29.173.233/cloud-images/testpmdvm-latest.qcow2'}
        if image_name not in images.keys():
            raise ValueError('Image "{}" is not known'.format(image_name))
        return CloudImage(name=image_name, url=images[image_name], cloud=cloud)


class Cloud(WithLogMixIn):
    ROLE_CONTROLLER = 'controller'
    ROLE_UCSM = 'ucsm'
    ROLE_NETWORK = 'network'
    ROLE_COMPUTE = 'compute'
    ROLE_MEDIATOR = 'mediator'

    def __init__(self, name, mediator, openrc_path, openrc_body):
        self._show_subnet_cmd = 'neutron subnet-show -f shell '

        self._provider_physical_network = 'Default Value Set In Cloud.__init__()'
        self._openstack_version = 'Default Value Set In Cloud.__init__()'

        self._name = name
        self._openrc_path = openrc_path
        self._os_sqe_password = 'os-sqe'
        self._username,  self._tenant, self._password, self._end_point = self.process_openrc(openrc_as_string=openrc_body)
        self._mediator = mediator  # special server to be used to execute CLI commands for this cloud
        self._instance_counter = 0  # this counter is used to count how many instances are created via this class
        service_lst = self.os_host_list()
        self._controls = sorted([x['Host Name'] for x in service_lst if x['Service'] == 'scheduler'])
        self._computes = sorted([x['Host Name'] for x in service_lst if x['Service'] == 'compute'])

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
        return 'Cloud {}: {} {} {}'.format(self._name, self._username, self._password, self._end_point)

    @staticmethod
    def _add_name_prefix(name):
        return '{}-{}'.format(UNIQUE_PATTERN_IN_NAME, name)

    def get_computes(self):
        return self._computes

    def get_name(self):
        return self._name

    def get_mediator(self):
        return self._mediator

    def get_lab(self):
        return self._mediator.lab()

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
        server = server or self._mediator
        cmd = 'source {} && {}  {}'.format(self._openrc_path, cmd, comment)
        ans = server.exe(command=cmd, is_warn_only=is_warn_only)
        if '-f csv' in cmd:
            return self._process_csv_output(ans)
        elif '-f json' in cmd:
            return self._process_json_output(ans)
        elif '-f shell' in cmd:
            return self._process_shell_output(answer=ans, command=cmd)
        else:
            return self._process_shell_output(answer=ans, command=cmd)

    @staticmethod
    def _filter(minus_c, flt):
        return '{c} {g}'.format(c='-c ' + minus_c if minus_c else '', g=' | grep ' + flt if flt else '')

    @staticmethod
    def _process_json_output(answer):
        import json

        try:
            ans = json.loads(answer)
        except ValueError:  # this may happen e.g. openstack image show non-existing -f json which gives "Could not find resource sqe-test-iperf"
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
    def _process_shell_output(command, answer):
        if 'delete' in command or not answer:
            return []
        else:
            lines = answer.split('\r\n')
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

    def create_router(self, number, on_nets, fip_net):
        router_name = self._add_name_prefix('-router-' + str(number))
        self.os_cmd('neutron router-create ' + router_name)
        for net in sorted(on_nets):
            self.os_cmd('neutron router-interface-add {} {}'.format(router_name, net.get_subnet_name()))
        self.os_cmd('neutron router-gateway-set {} {}'.format(router_name, fip_net.get_net_name()))

    def list_ports(self, network_id=None):
        query = ' '.join(['--network-id=' + network_id if network_id else ''])
        return self.os_cmd('neutron port-list -f csv {q}'.format(q=query))

    def show_port(self, port_id):
        return self.os_cmd('neutron port-show {0} -f shell'.format(port_id))

    def os_create_fips(self, fip_net, how_many):
        return map(lambda _: self.os_cmd('neutron floatingip-create {0}'.format(fip_net.get_net_name())), range(how_many))

    @section('Creating custom flavor')
    def os_flavor_create(self, name):
        name_with_prefix = self._add_name_prefix(name)
        res = self.os_cmd('openstack flavor create {} --vcpu 2 --ram 4096 --disk 40 --public -f shell'.format(name_with_prefix))
        self.os_cmd('openstack flavor set {} --property hw:numa_nodes=1'.format(name_with_prefix))
        self.os_cmd('openstack flavor set {} --property hw:mem_page_size=large'.format(name_with_prefix))
        return res

    def os_flavor_delete(self, flavors):
        map(lambda x: self.os_cmd('openstack flavor delete {}'.format(x['Name'])), flavors)

    def os_flavor_list(self):
        return self.os_cmd('openstack flavor list -f json')

    def os_server_reboot(self, server, hard=False):
        flags = ['--hard' if hard else '--soft']
        self.os_cmd('openstack server reboot {} {}'.format(flags, server['ID']), comment='# server {}'.format(server['Name']))
        self.wait_instances_ready(servers=[server])

    def os_server_rebuild(self, server, image):
        self.os_cmd('openstack server rebuild {} --image {}'.format(server['ID'], image), comment='# {}'.format(server['Name']))
        self.wait_instances_ready(servers=[server])

    def os_server_suspend(self, server):
        self.os_cmd('openstack server suspend {}'.format(server['ID']))
        self.wait_instances_ready([server], status='SUSPENDED')

    def os_server_resume(self, server):
        self.os_cmd('openstack server resume {}'.format(server['ID']), comment='# server {}'.format(server['Name']))
        self.wait_instances_ready(servers=[server])

    def wait_instances_ready(self, servers, status='ACTIVE', timeout=300):
        import time

        required_n_servers = 0 if status == 'DELETED' else len(servers)
        our_ids = [s['ID'] for s in servers]
        start_time = time.time()
        while True:
            all_instances = self.os_server_list()
            our_instances = filter(lambda x: x['ID'] in our_ids, all_instances)
            instances_in_error = filter(lambda x: x['Status'] == 'ERROR', our_instances)
            instances_in_status = filter(lambda x: x['Status'] == status, our_instances) if status != 'DELETED' else our_instances
            if len(instances_in_status) == required_n_servers:
                return  # all successfully reached the status
            if instances_in_error:
                for instance in instances_in_error:
                    self.analyse_instance_problems(instance)
                raise RuntimeError('These instances failed: {0}'.format(instances_in_error))
            if time.time() > start_time + timeout:
                raise RuntimeError('Instances {} are not active after {} secs'.format(our_instances, timeout))
            time.sleep(30)

    def analyse_instance_problems(self, instance):
        instance_details = self.os_server_show(instance['Name'])
        raise RuntimeError(instance_details['fault']['message'])

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
                ans[host] = self._mediator.exe("ssh -o StrictHostKeyChecking=no {} '{}'".format(host, cmd), is_warn_only=True)
        except:
            ans['This cloud is not active'] = ''
        return ans

    def os_host_list(self):
        return self.os_cmd('openstack host list -f json')

    def os_image_create(self, image_name):
        return CloudImage.add_image(image_name=image_name, cloud=self)

    def os_image_analyse_problem(self, image):
        self.r_collect_information(regex=image['Name'], comment='image problem')
        raise RuntimeError('image {} failed'.format(image['name']))

    def os_image_delete(self, images):
        map(lambda x: self.os_cmd(cmd='openstack image delete ' + x['ID'], comment='# image name ' + x['Name']), images)

    def os_image_list(self):
        return self.os_cmd('openstack image list -f json')

    def os_image_show(self, name):
        return self.os_cmd('openstack image show -f json {}'.format(name), is_warn_only=True)

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

    @section('Creating key pair', estimated_time=5)
    def os_keypair_create(self):
        from lab import with_config
        with open(with_config.KEY_PUBLIC_PATH) as f:
            public_path = self._mediator.r_put_string_as_file_in_dir(string_to_put=f.read(), file_name='sqe_public_key')

        self.os_cmd('openstack keypair create {} --public-key {}'.format(self._add_name_prefix('key1'), public_path))

    def os_keypair_delete(self, keypairs):
        map(lambda x: self.os_cmd('openstack keypair delete {}'.format(x['Name'])), keypairs)

    def os_keypair_list(self):
        return self.os_cmd('openstack keypair list -f json')

    def os_network_create(self, net):
        net_status = self.os_cmd(net.get_net_cmd())
        subnet_status = self.os_cmd(net.get_subnet_cmd())
        return net_status, subnet_status

    def os_network_delete(self, networks):
        map(lambda x: self.os_cmd(cmd='openstack network delete ' + x['ID'], comment='# net name ' + x['Name']), networks)

    def os_network_list(self):
        return self.os_cmd('openstack network list -f json')

    def os_port_create(self, server_number, net_name, ip, mac, sriov=False):
        sriov_addon = '--binding:vnic-type direct' if sriov else ''
        fixed_ip_addon = '--fixed-ip ip_address={ip} --mac-address {mac}'.format(ip=ip, mac=mac) if ip else ''
        port_name = self._add_name_prefix('{}-port-{}-on-{}'.format(server_number, 'sriov' if sriov else 'virio', net_name))
        return self.os_cmd('neutron port-create -f json --name {port_name} {net_name} {ip_addon} {sriov_addon}'.format(port_name=port_name, net_name=net_name, ip_addon=fixed_ip_addon, sriov_addon=sriov_addon))

    def os_port_delete(self, ports):
        map(lambda x: self.os_cmd(cmd='neutron port-delete ' + x['id'], comment='# port ' + x['name']), ports)

    def os_port_list(self):
        return self.os_cmd('neutron port-list -f json')

    def os_router_list(self):
        return self.os_cmd('neutron router-list -f json')

    def os_server_create(self, srv_name, flavor_name, image_name, zone_name, port_ids):
        ports_part = ' '.join(map(lambda x: '--nic port-id=' + x, port_ids))
        return self.os_cmd('openstack server create {} --flavor {} --image "{}" --availability-zone nova:{} --security-group default --key-name sqe-key1 {}'.format(srv_name, flavor_name, image_name, zone_name, ports_part))

    def os_server_delete(self, servers):
        if len(servers):
            ids = [s['ID'] for s in servers]
            names = [s['Name'] for s in servers]
            self.os_cmd('openstack server delete ' + ' '.join(ids), comment='# server names ' + ' '.join(names))
            self.wait_instances_ready(servers=servers, status='DELETED')

    def os_server_list(self):
        return self.os_cmd('openstack server list -f json')

    def os_server_show(self, name):
        return self.os_cmd('openstack server show -f json {}'.format(name))

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
            self.os_cmd('nova server-group-delete ' + ' '.join(ids), comment='# server groups ' + ' '.join(names))

    def os_user_list(self):
        return self.os_cmd('openstack user list -f json')

    def os_user_create(self, user_name):
        return self.os_cmd('openstack user create --password {} {} -f json'.format(self._os_sqe_password, user_name))

    def os_user_delete(self, users):
        map(lambda x: self.os_cmd('openstack user delete {}'.format(x['ID']), comment='# user {}'.format(x['Name'])), users)

    def os_cleanup(self, is_all=False):
        servers = self.os_server_list()

        if not is_all:  # first servers then all others since servers usually reserves ports
            servers = filter(lambda s: UNIQUE_PATTERN_IN_NAME in s['Name'], servers)

        self.os_server_delete(servers=servers)

        routers = self.os_router_list()
        ports = self.os_port_list()
        keypairs = self.os_keypair_list()
        networks = self.os_network_list()
        flavors = self.os_flavor_list()
        images = self.os_image_list()
        server_groups = self.os_server_group_list()
        security_groups = [x for x in self.os_security_group_list() if x['Name'] != 'default']  # don not delete default security group
        users = [x for x in self.os_user_list() if x['Name'] not in ['admin', 'glance', 'neutron', 'cinder', 'nova', 'cloudpulse']]

        if not is_all:
            ports = filter(lambda p: UNIQUE_PATTERN_IN_NAME in p['name'], ports)
            networks = filter(lambda n: UNIQUE_PATTERN_IN_NAME in n['Name'], networks)
            routers = filter(lambda r: UNIQUE_PATTERN_IN_NAME in r['name'], routers)
            keypairs = filter(lambda k: UNIQUE_PATTERN_IN_NAME in k['Name'], keypairs)
            flavors = filter(lambda f: UNIQUE_PATTERN_IN_NAME in f['Name'], flavors)
            images = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], images)
            server_groups = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], server_groups)
            security_groups = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], security_groups)
            users = filter(lambda i: UNIQUE_PATTERN_IN_NAME in i['Name'], users)

        self._clean_router(routers=routers)
        self.os_port_delete(ports=ports)
        self.os_network_delete(networks=networks)
        self.os_keypair_delete(keypairs=keypairs)
        self.os_flavor_delete(flavors=flavors)
        self.os_image_delete(images=images)
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
        self.log_to_artifact(name='cloud_{}{}.txt'.format(self._name, addon), body=body)
        return body

    def _clean_router(self, routers):
        import re

        for router in routers:
            router_name = router['name']
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
