from lab import decorators
from lab.nodes.virtual_server import VipServer, LibVirtServer


class Vtc(VipServer):
    """
    set cisco-vts devices device TORSWITCHB ports port Ethernet1/39 connection-type server
    set cisco-vts devices device TORSWITCHB ports port Ethernet1/39 servers server nfvbench_tg type baremetal
    set cisco-vts devices device TORSWITCHB ports port Ethernet1/39 servers server nfvbench_tg interface-name eth0
    set cisco-vts devices device TORSWITCHB ports port Ethernet1/39 servers server nfvbench_tg ip 1.1.1.1


    set cisco-vts devices device TORSWITCHA ports port Ethernet1/39 connection-type server
    set cisco-vts devices device TORSWITCHA ports port Ethernet1/39 servers server nfvbench_tg type baremetal
    set cisco-vts devices device TORSWITCHA ports port Ethernet1/39 servers server nfvbench_tg interface-name eth1
    set cisco-vts devices device TORSWITCHA ports port Ethernet1/39 servers server nfvbench_tg ip 1.1.1.1
    """

    API_CALLS = {
        'get_vtc_ha':            {'rest': '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/vtc-ha?deep',                             'cli': 'show configuration vtc-ha'},
        'get_openstack':         {'rest': '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/openstack?deep',                          'cli': 'show configuration openstack vmm'},
        'get_devices':           {'rest': '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/cisco-vts/devices?deep',                  'cli': 'show configuration cisco-vts devices device'},
        'get_servers':           {'rest': '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/cisco-vts/uuid-servers?deep',             'cli': 'show configuration cisco-vts uuid-servers'},
        'get_pools':             {'rest': '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/resource-pools?deep',                     'cli': 'show configuration resource-pools'},

        'del_port':              {'rest': '-XDELETE https://{ip}:8888/api/running/cisco-vts/tenants/tenant/admin/topologies/topology/admin/ports/port', 'cli': ''},
        'del_network':           {'rest': '-XDELETE https://{ip}:8888/api/running/openstack/vmm/{uuid}/network', 'cli': ''},
        'del_subnet':            {'rest': '-XDELETE https://{ip}:8888/api/running/openstack/vmm/{uuid}/subnet', 'cli': ''},


        'del_operations':        {'rest': '-XDELETE https://{ip}:8888/{uuid}', },  # exec operation listed in operations

        'post_sync_from':        {'rest': '-XPOST https://{ip}:8888//api/running/devices/device/{uuid}/_operations/sync-from',                                       'cli': ''},

        'put_server':            {'rest': "-XPUT -H 'Content-Type: application/vnd.yang.data+json' https://{ip}:8888/api/running/cisco-vts/uuid-servers/uuid-server/{uuid} -d '{data}'"},
        'patch_device_port':     {'rest': "-XPATCH -H 'Content-Type: application/vnd.yang.data+json' https://{ip}:8888/api/running/cisco-vts/devices/device/{uuid}/ports -d '{data}'",
                                  'json': '{"cisco-vts:ports": {"port": [{"name": "PORT", "connection-type": "cisco-vts-identities:server", "servers": {"server": [{"name": "NAME", "type": "cisco-vts-identities:baremetal", "interface-name": "eth0", "ip": "1.1.1.1"}]}}]}}'
                                 }
    }

    def __init__(self, pod, dic):
        super(Vtc, self).__init__(pod=pod, dic=dic)
        self.vtc_username = dic['vtc-username']
        self.vtc_password = dic['vtc-password']

    def cmd(self, cmd, uuid='', uuid1='', dic=None):
        import json

        if cmd not in self.API_CALLS:
            raise ValueError('{}: API CALL "{}" is not supported'.format(self, cmd))

        cmd = 'curl -s -k -u {u}:{p} '.format(u=self.vtc_username, p=self.vtc_password) + self.API_CALLS[cmd]['rest'].format(ip=self.ssh_ip, uuid=uuid, uuid1=uuid1, data=dic)
        for i in range(10):
            ans = self.exe(cmd, is_warn_only=True)
            if ans.failed:
                raise RuntimeError(ans)
            else:
                try:  # sometimes the answer is not fully formed (usually happens with server list), simply repeat
                    return json.loads(ans) if ans else {}  # it might be empty
                except ValueError:  # something like ValueError: Unterminated string starting at: line 65 column 11 (char 4086)
                    continue
        else:
            raise RuntimeError('Failed after 10 attempts: ' + cmd)

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.pod.get_vft())

    def disrupt(self, node_to_disrupt, method_to_disrupt, downtime):
        import time

        is_master = node_to_disrupt.startswith('master')
        node_class = node_to_disrupt.split('-')[-1]
        cluster = self.r_vtc_get_ha()

        node_id = [x['hostname'] for x in cluster['vtc-ha:vtc-ha']['nodes']['node'] if x['original-state'] == ('Master' if is_master else 'Slave')][0]
        node_id = node_id.replace('vtc', node_class)  # node_id might by vtcXX or vtsrXX

        node_disrupt = self.individuals[node_id]

        vts_host = node_disrupt.hard

        if method_to_disrupt == 'vm-shutdown':
            vts_host.exe(command='virsh suspend {}'.format(self.id))
            time.sleep(downtime)
            vts_host.exe(command='virsh resume {}'.format(self.id))
        elif method_to_disrupt == 'isolate-from-mx':
            ans = vts_host.exe('ip l | grep mgmt | grep {0}'.format(self.id))
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} down'.format(if_name))
            time.sleep(downtime)
            vts_host.exe('ip l s dev {} up'.format(if_name))
        elif method_to_disrupt == 'isolate-from-api':
            ans = vts_host.exe('ip l | grep api | grep {0}'.format(self.id))
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} down'.format(if_name))
            time.sleep(downtime)
            vts_host.exe('ip l s dev {} up'.format(if_name))
        elif method_to_disrupt == 'vm-reboot':
            # 'set -m' because of http://stackoverflow.com/questions/8775598/start-a-background-process-with-nohup-using-fabric
            self.exe('set -m; sudo bash -c "ip link set dev eth0 down && ip link set dev eth1 down && sleep {0} && shutdown -r now" 2>/dev/null >/dev/null &'.format(downtime), is_warn_only=True)
            time.sleep(downtime)

    def get_config_and_net_part_bodies(self):
        from lab import with_config

        cfg_tmpl = with_config.read_config_from_file(cfg_path='vtc-vm-config.txt', folder='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(cfg_path='vtc-net-part-of-libvirt-domain.template', folder='vts', is_as_string=True)

        dns_ip, ntp_ip = self.pod.get_dns()[0], self.pod.get_ntp()[0]
        hostname = '{id}-{lab}'.format(lab=self.pod, id=self.id)

        a_nic = self.get_nic('a')  # Vtc sits on out-of-tor network marked is_ssh
        a_ip, a_net_mask = a_nic.get_ip_and_mask()
        a_gw = a_nic.get_net().get_gw()

        mx_nic = self.get_nic('mx')  # also sits on mx network
        mx_ip, mx_net_mask = mx_nic.get_ip_and_mask()
        mx_vlan = mx_nic.get_net().get_vlan_id()

        cfg_body = cfg_tmpl.format(vtc_a_ip=a_ip, a_net_mask=a_net_mask, a_gw=a_gw, vtc_mx_ip=mx_ip, mx_net_mask=mx_net_mask, dns_ip=dns_ip, ntp_ip=ntp_ip, username=self.ssh_username, password=self.ssh_password, hostname=hostname)
        net_part = net_part_tmpl.format(a_nic_name='a', mx_nic_name='mx', mx_vlan=mx_vlan)

        with with_config.WithConfig.open_artifact(hostname, 'w') as f:
            f.write(cfg_body)
        return cfg_body, net_part

    def get_cluster_conf_body(self):
        from lab import with_config

        vip_a, vip_mx = self.ssh_ip
        a_ip = []
        mx_ip = []
        mx_gw = None
        for node_id in ['bld', 'vtc1', 'vtc2']:
            a_ip.append(self.pod.get_node_by_id(node_id=node_id).get_nic('a').get_ip_and_mask()[0])
            mx_nic = self.pod.get_node_by_id(node_id=node_id).get_nic('mx')
            mx_gw = mx_nic.get_gw()

            mx_ip.append(mx_nic.get_ip_and_mask()[0])
        cfg_tmpl = with_config.read_config_from_file(cfg_path='cluster.conf.template', folder='vts', is_as_string=True)
        cfg_body = cfg_tmpl.format(lab_name=self.pod, vip_a=vip_a, vip_mx=vip_mx, vtc1_a_ip=a_ip[1], vtc2_a_ip=a_ip[2], vtc1_mx_ip=mx_ip[1], vtc2_mx_ip=mx_ip[2], special_ip=a_ip[0], mx_gw=mx_gw)
        with with_config.WithConfig.open_artifact('cluster.conf', 'w') as f:
            f.write(cfg_body)
        return cfg_body

    def vtc_change_default_password(self):
        import json
        import re
        import requests
        from time import sleep

        default_username, default_password = 'admin', 'admin'

        if default_username != self.oob_username:
            raise ValueError

        api_security_check = 'https://{}:8443/VTS/j_spring_security_check'.format(self.ssh_ip)
        api_java_servlet = 'https://{}:8443/VTS/JavaScriptServlet'.format(self.ssh_ip)
        api_update_password = 'https://{}:8443/VTS/rs/ncs/user?updatePassword=true&isEnforcePassword=true'.format(self.ssh_ip)

        while True:
            # noinspection PyBroadException
            try:
                self.log(message='Waiting for VTC service up...')
                requests.get('https://{}:8443/VTS/'.format(self.ssh_ip), verify=False, timeout=300)  # First try to open to check that Tomcat is indeed started
                break
            except:
                sleep(100)

        session = requests.Session()
        auth = session.post(api_security_check, data={'j_username': default_username, 'j_password': default_password, 'Submit': 'Login'}, verify=False)
        if 'Invalid username or passphrase' in auth.text:
            raise ValueError(auth.text)

        java_script_servlet = session.get(api_java_servlet, verify=False)
        owasp_csrftoken = ''.join(re.findall(r'OWASP_CSRFTOKEN", "(.*?)", requestPageTokens', java_script_servlet.text))

        response = session.put(api_update_password,
                               data=json.dumps({'resource': {'user': {'user_name': self.oob_username, 'password': self.oob_password, 'currentPassword': default_password}}}),
                               headers={'OWASP_CSRFTOKEN': owasp_csrftoken,
                                        'X-Requested-With': 'OWASP CSRFGuard Project',
                                        'Accept': 'application/json, text/plain, */*',
                                        'Accept-Encoding': 'gzip, deflate, sdch, br',
                                        'Content-Type': 'application/json;charset=UTF-8'})

        if response.status_code == 200 and 'Error report' not in response.text:
            self.log(message='password changed')
            return response.text
        else:
            raise RuntimeError(response.text)

    def r_vtc_get_ha(self):
        return self.cmd('get_vtc_ha')

    def r_vtc_wait_cluster_formed(self, n_retries=1):
        import requests.exceptions

        nodes = self.pod.get_nodes_by_class(Vtc)
        while True:
            try:
                cluster = self.cmd('get_vtc_ha')
                break
            except requests.exceptions.ConnectTimeout:
                n_retries -= 1
                if n_retries == 0:
                    return False
                else:
                    continue

        reported_ips = [x['address'] for x in cluster['collection']['tcm:members']]
        for node in nodes:
            if node.get_ssh()[0] not in reported_ips:
                return False
        return True

    def r_collect_info(self, regex):
        body = ''
        for cmd in [self.log_grep_cmd(log_files='/opt/vts/log/nso/*', regex=regex), self.log_grep_cmd(log_files='/opt/vts/log/nso/localhost\:8888.access', regex='HTTP/1.1" 40')]:
            ans = self.exe(cmd, is_warn_only=True)
            body += self.single_cmd_output(cmd=cmd, ans=ans)
        return body

    def r_vtc_day0_config(self):  # https://cisco.jiveon.com/docs/DOC-1469629
        import jinja2

        domain = jinja2.Template('''
            set resource-pools vni-pool vnipool range 4096 65535

            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 policy-parameters distribution-mode decentralized-l2
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 policy-parameters control-plane-protocol bgp-evpn
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 policy-parameters arp-suppression
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 policy-parameters packet-replication ingress-replication
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l3-gateway-groups l3-gateway-group L3GW-0 policy-parameters distribution-mode decentralized-l3
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l3-gateway-groups l3-gateway-group L3GW-0 policy-parameters control-plane-protocol bgp-evpn
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l3-gateway-groups l3-gateway-group L3GW-0 policy-parameters arp-suppression
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l3-gateway-groups l3-gateway-group L3GW-0 policy-parameters packet-replication ingress-replication
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 ad-l3-gw-parent L3GW-0''')
        xrvr = jinja2.Template('''{% for xrvr_name in xrvr_names %}
            request devices device {{ xrvr_name }} sync-from
            set devices device {{ xrvr_name }} asr9k-extension:device-info device-use leaf
            set devices device {{ xrvr_name }} asr9k-extension:device-info bgp-peering-info bgp-asn {{ bgp_asn }}
            set devices device {{ xrvr_name }} asr9k-extension:device-info bgp-peering-info loopback-if-num 0
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 devices device {{ xrvr_name }}
            {% endfor %}''')
        tmpl_switches = jinja2.Template('''
            {% for switch in switches %}
            set devices authgroups group {{ switch['id'] }} umap admin remote-name {{ switch['username'] }}
            set devices authgroups group {{ switch['id'] }} umap admin remote-password {{ switch['password'] }}
            set resource-pools vlan-pool {{ switch['id'] }} range 3000 3999
            set devices device {{ switch['id'] }} address {{ switch['ip'] }}
            set devices device {{ switch['id'] }} authgroup {{ switch['id'] }}
            set devices device {{ switch['id'] }} device-type cli ned-id cisco-nx
            set devices device {{ switch['id'] }} device-type cli protocol telnet
            set devices device {{ switch['id'] }} n9k-extension:device-info platform N9K
            set devices device {{ switch['id'] }} n9k-extension:device-info device-use leaf
            set devices device {{ switch['id'] }} state admin-state unlocked
            commit
            request devices device {{ switch['id'] }} sync-from
            set devices device {{ switch['id'] }} n9k-extension:device-info bgp-peering-info bgp-asn {{ bgp_asn }}
            set devices device {{ switch['id'] }} n9k-extension:device-info bgp-peering-info loopback-if-num 0
            set cisco-vts infra-policy admin-domains admin-domain {{ domain_group }} l2-gateway-groups l2-gateway-group L2GW-0 devices device {{ switch['id'] }}
            {% endfor %}''')
        sync = jinja2.Template('''
            {% for name in names %}
            request devices device {{ name }} sync-from
            {% endfor %}''')

        map(lambda y: y.r_xrvr_day0_config(), self.pod.get_xrvr())
        self.r_vtc_ncs_cli(command=domain.render(domain_group='D1'))
        self.r_vtc_ncs_cli(command=xrvr.render(xrvr_names=['xrvr1', 'xrvr2'], domain_group='D1', bgp_asn=23))

        switches = [{'id': x.get_id(), 'ip': x.get_oob()[0], 'username': x.get_oob()[1], 'password': x.get_oob()[2]} for x in self.pod.tors]
        self.r_vtc_ncs_cli(command=tmpl_switches.render(switches=switches, domain_group='D1', bgp_asn=23))

        self.r_vtc_ncs_cli(command=sync.render(names=['xrvr1', 'xrvr2'] + ['n91', 'n92']))

    def r_vtc_delete_openstack_objects(self, is_via_ncs=True):
        members = self.cmd('get')
        master_name = [x['name'] for x in members if x['status'] == 'master'][0]

        master = self.pod.get_node_by_id(master_name)
        if is_via_ncs:
            master.r_vtc_ncs_cli('delete openstack port\ndelete openstack subnet\ndelete openstack network')
        else:
            return NotImplemented()

    def r_vtc_ncs_cli(self, command):
        self.exe('ncs_cli << EOF\nconfigure\n{}\ncommit\nexit\nexit\nEOF'.format(command))

    @decorators.section('Get VTS version')
    def r_vtc_get_version(self):
        return self.exe('version_info')

    def r_vtc_show_tech_support(self):
        wild_card = 'VTS*tar.bz2'
        self.exe('show_tech_support')
        ans = self.exe('ls ' + wild_card)
        self.r_get_file_from_dir(rem_rel_path=ans, loc_abs_path='artifacts/vst_tech_support.bz2')
        self.exe('rm -r ' + wild_card)

    def r_vtc_get_all(self):
        self.r_vtc_cluster_status()
        [self.cmd(x) for x in sorted(self.API_CALLS.keys()) if x.startswith('get_')]

    def r_vtc_cluster_status(self):
        return self.exe('sudo crm status', is_warn_only=True)

    @decorators.section('Clean up VTS')
    def r_vtc_delete_openstack(self):
        self.cmd('del_port')
        r = self.cmd('get_openstack')
        if not r:
            return
        for vmm_dic in r['cisco-vts-openstack:openstack']['vmm']:
            vmm_id = vmm_dic['id']
            self.cmd('del_subnet', uuid=vmm_id)
            self.cmd('del_network', uuid=vmm_id)

    @decorators.section('Add baremetal to VTC host inventory')
    def r_vtc_add_host_to_inventory(self, server_name, tor_name, tor_port):
        """
        :param server_name: name of server as you need to have it in barametal inventory, e.g. nfvbench_tg
        :param tor_name: name of TOR as it's seen in VTC get devices API CALL, e.g. TORSWITCHA
        :param tor_port:  TOR switch port to which this server is connected e.g. Ethernet1/19
        :return: nothing
        """
        self.cmd(cmd='patch_device_port', uuid=tor_name, dic=self.API_CALLS['patch_device_port']['json'].replace('NAME', server_name).replace('PORT', tor_port))

    def r_vtc_create_border_leaf_port(self, os_networks):
        import uuid
        import json
        from collections import OrderedDict

        a = self.cmd('get_pools')
        vlan_start, vlan_end = 1 ,2

        vlan = (vlan_start + vlan_end) / 2
        srvs = self.cmd(cmd='get_servers')
        mgmt_srv = [srv for srv in srvs if 'baremetal' in srv['server-type'] and 'nfvbench' not in srv['server-id']][0]
        tenant = 'admin'

        for network in os_networks:
            port_id = str(uuid.uuid4())
            new_uuid = str(uuid.uuid4())
            port_dict = OrderedDict()
            port_dict['id'] = port_id
            port_dict['network-id'] = network.get_net_id()
            port_dict['admin-state-up'] = True
            port_dict['status'] = 'cisco-vts-identities:active'
            port_dict['binding-host-id'] = mgmt_srv['server-id']
            port_dict['vlan-id'] = vlan
            network.set_vts_vlan(vlan)
            vlan += 1
            port_dict['mac-address'] = 'unknown-' + new_uuid
            port_dict['connid'] = [{'id': mgmt_srv['connid']}]
            port_data = {'port': port_dict}

            port_json = json.dumps(port_data)
            self.cmd(cmd='put_port', ).put(url='/api/running/cisco-vts/tenants/tenant/admin/topologies/topology/admin/ports/port/{1}'.format(tenant, port_id), data=port_json)

    def r_vtc_delete_border_leaf_port(self):
        import time

        ports = self.cmd('get_ports')
        if len(ports) == 0:
            return

        baremetal_host_ids = [srv for srv in self.cmd('get_servers') if 'baremetal' in srv['server-type']]

        for port in ports:
            if port['biding-host-id'] in baremetal_host_ids:
                self.cmd('del_operations', uuid=port['operations']['un-deploy'])
                time.sleep(15)  # if try to delete 2 ports without delay, one may have TOR out of sync


class VtcIndividual(LibVirtServer):
    pass
