from lab import decorators
from lab.nodes.cimc_server import CimcServer
from lab.nodes.virtual_server import VirtualServer


class Vtc(VirtualServer):
    ROLE = 'vtc'

    def __init__(self, **kwargs):
        super(Vtc, self).__init__(**kwargs)
        self._vip_a, self._vip_mx = 'Default in Vtc.__init()', 'Default in Vtc.__init()'
        self._is_api_via_vip = True
        self.set_vip(kwargs['vip'], kwargs['nics']['mx']['ip'])

    def disable_vip(self):
        self._is_api_via_vip = False

    def _rest_api(self, resource, headers, data=None, params=None):
        import requests
        import json
        # from requests.packages import urllib3

        # urllib3.disable_warnings()  # Suppressing warning due to self-signed certificate

        type_of_call, url_path = resource.split()
        url_path = url_path.strip('/')
        _, username, password = self.get_oob()
        vip = self.get_vtc_vips()[0] if self._is_api_via_vip else self._server.get_ssh_ip()
        url = 'https://{ip}:{port}/{resource}'.format(ip=vip, port=8888, resource=url_path)
        auth = (username, password)

        try:
            if type_of_call in ['get', 'GET']:
                ans = requests.get(url, auth=auth, headers=headers, params=params, timeout=100, verify=False)
            elif type_of_call in ['patch', 'PATCH']:
                ans = requests.patch(url, auth=auth, headers=headers, data=data, timeout=100, verify=False)
            elif type_of_call in ['put', 'PUT']:
                ans = requests.put(url, auth=auth, headers=headers, data=data, timeout=100, verify=False)
            else:
                raise ValueError('Unsupported type of call: "{}"'.format(type_of_call))
            if ans.ok:
                d = {'call': resource}
                if ans.text:
                    d.update(json.loads(ans.text))
                return d
            else:
                raise RuntimeError('for {}: {}'.format(resource, ans.text or ans.reason))
        except requests.ConnectTimeout:
            self.log(message='Url={url} auth={auth}, headers={headers}, param={params}'.format(url=url, auth=auth, headers=headers, params=params), level='exception')
            raise
        except Exception as e:
            raise RuntimeError('{}({}) when doing {} {} with {}'.format(type(e), e, e.request.method, e.request.url, e.request.headers))

    def set_vip(self, vip, vip_mx):
        self._vip_a, self._vip_mx = vip, vip_mx

    def get_vtc_vips(self):
        return self._vip_a, self._vip_mx

    def cmd(self, cmd, **kwargs):
        return self._rest_api(resource=cmd, headers={})

    def get_vtf(self):
        from lab.nodes.vtf import Vtf

        return self.lab().get_nodes_by_class(Vtf)

    def get_xrvr_names(self):
        return map(lambda x: x.get_id(), self.lab().get_xrvr())

    def r_vtc_get_vtfs(self):
        ans = self._rest_api(resource='GET /api/running/cisco-vts', headers={'Accept': 'application/vnd.yang.data+json'})
        vtf_ips_from_vtc = [x['ip'] for x in ans['cisco-vts:cisco-vts']['vtfs']['vtf']]
        vtf_nodes = self.get_vtf()
        for vtf in vtf_nodes:
            _, username, password = vtf.get_oob()
            vtf.set_oob_creds(ip=vtf_ips_from_vtc.pop(0), username=username, password=password)
        return vtf_nodes

    def r_vtc_get_xrvrs(self):
        xrvr_nodes = self.lab().get_xrvr()
        devices = self.r_vtc_show_devices_device()
        if 'collection' not in devices:
            return []
        xrvr_ips_from_vtc = [x['address'] for x in devices['collection']['tailf-ncs:device']]
        for xrvr in xrvr_nodes:
            if str(xrvr.get_ip_mx()) not in xrvr_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(xrvr, self))
        return xrvr_nodes

    def xrvr_restart_dl(self):
        return map(lambda xrvr: xrvr.xrvr_restart_dl(), self.lab().get_xrvr())

    def show_connections_xrvr_vtf(self):
        return map(lambda vtf: vtf.show_connections_xrvr_vtf(), self.get_vtf()) + map(lambda xrvr: xrvr.xrvr_show_connections_xrvr_vtf(), self.lab().get_xrvr())

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.lab().get_vft())

    def disrupt(self, method_to_disrupt, downtime):
        import time

        vts_host = [x.get_peer_node(self) for x in self.get_all_wires() if x.get_peer_node(self).is_vts_host()][0]

        if method_to_disrupt == 'vm-shutdown':
            vts_host.exe(command='virsh suspend {}'.format(self.get_node_id()))
            time.sleep(downtime)
            vts_host.exe(command='virsh resume {}'.format(self.get_node_id()))
        elif method_to_disrupt == 'isolate-from-mx':
            ans = vts_host.exe('ip l | grep mgmt | grep {0}'.format(self.get_node_id()))
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} down'.format(if_name))
            time.sleep(downtime)
            vts_host.exe('ip l s dev {} up'.format(if_name))
        elif method_to_disrupt == 'isolate-from-api':
            ans = vts_host.exe('ip l | grep api | grep {0}'.format(self.get_node_id()))
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

        cfg_tmpl = with_config.read_config_from_file(config_path='vtc-vm-config.txt', directory='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(config_path='vtc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        dns_ip, ntp_ip = self.lab().get_dns()[0], self.lab().get_ntp()[0]
        hostname = '{id}-{lab}'.format(lab=self.lab(), id=self.get_node_id())

        _, ssh_username, ssh_password = self._server.get_ssh()

        a_nic = self.get_nic('a')  # Vtc sits on out-of-tor network marked is_ssh
        a_ip, a_net_mask = a_nic.get_ip_and_mask()
        a_gw = a_nic.get_net().get_gw()

        mx_nic = self.get_nic('mx')  # also sits on mx network
        mx_ip, mx_net_mask = mx_nic.get_ip_and_mask()
        mx_vlan = mx_nic.get_net().get_vlan_id()

        cfg_body = cfg_tmpl.format(vtc_a_ip=a_ip, a_net_mask=a_net_mask, a_gw=a_gw, vtc_mx_ip=mx_ip, mx_net_mask=mx_net_mask, dns_ip=dns_ip, ntp_ip=ntp_ip, username=ssh_username, password=ssh_password, hostname=hostname)
        net_part = net_part_tmpl.format(a_nic_name='a', mx_nic_name='mx', mx_vlan=mx_vlan)

        with with_config.WithConfig.open_artifact(hostname, 'w') as f:
            f.write(cfg_body)
        return cfg_body, net_part

    def get_cluster_conf_body(self):
        from lab import with_config

        vip_a, vip_mx = self.get_vtc_vips()
        a_ip = []
        mx_ip = []
        mx_gw = None
        for node_id in ['bld', 'vtc1', 'vtc2']:
            a_ip.append(self.lab().get_node_by_id(node_id=node_id).get_nic('a').get_ip_and_mask()[0])
            mx_nic = self.lab().get_node_by_id(node_id=node_id).get_nic('mx')
            mx_gw = mx_nic.get_gw()

            mx_ip.append(mx_nic.get_ip_and_mask()[0])
        cfg_tmpl = with_config.read_config_from_file(config_path='cluster.conf.template', directory='vts', is_as_string=True)
        cfg_body = cfg_tmpl.format(lab_name=self.lab(), vip_a=vip_a, vip_mx=vip_mx, vtc1_a_ip=a_ip[1], vtc2_a_ip=a_ip[2], vtc1_mx_ip=mx_ip[1], vtc2_mx_ip=mx_ip[2], special_ip=a_ip[0], mx_gw=mx_gw)
        with with_config.WithConfig.open_artifact('cluster.conf', 'w') as f:
            f.write(cfg_body)
        return cfg_body

    def vtc_change_default_password(self):
        import json
        import re
        import requests
        from time import sleep

        vtc_ip, _, _ = self._server.get_ssh()
        _, username, password = self.get_oob()
        default_username, default_password = 'admin', 'admin'

        if default_username != username:
            raise ValueError

        api_security_check = 'https://{}:8443/VTS/j_spring_security_check'.format(vtc_ip)
        api_java_servlet = 'https://{}:8443/VTS/JavaScriptServlet'.format(vtc_ip)
        api_update_password = 'https://{}:8443/VTS/rs/ncs/user?updatePassword=true&isEnforcePassword=true'.format(vtc_ip)

        while not self._server.ping():
            sleep(15)
        while not self._server.ping(8443):
            sleep(15)

        while True:
            # noinspection PyBroadException
            try:
                self.log(message='Waiting for VTC service up...')
                requests.get('https://{}:8443/VTS/'.format(vtc_ip), verify=False, timeout=300)  # First try to open to check that Tomcat is indeed started
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
                               data=json.dumps({'resource': {'user': {'user_name': username, 'password': password, 'currentPassword': default_password}}}),
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

    def r_vtc_wait_cluster_formed(self, n_retries=1):
        import requests.exceptions

        nodes = self.lab().get_nodes_by_class(Vtc)
        while True:
            try:
                cluster = self.r_vtc_show_ha_cluster_members()
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

    def r_collect_logs(self, regex):
        body = ''
        for cmd in [self._form_log_grep_cmd(log_files='/var/log/ncs/*', regex=regex), 'cat /var/log/ncs/localhost\:8888.access']:
            ans = self.exe(cmd, is_warn_only=True)
            body += self._format_single_cmd_output(cmd=cmd, ans=ans)
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

        map(lambda y: y.r_xrvr_day0_config(), self.lab().get_xrvr())
        self.r_vtc_ncs_cli(command=domain.render(domain_group='D1'))
        self.r_vtc_ncs_cli(command=xrvr.render(xrvr_names=self.get_xrvr_names(), domain_group='D1', bgp_asn=23))

        switches = [{'id': x.get_id(), 'ip': x.get_oob()[0], 'username': x.get_oob()[1], 'password': x.get_oob()[2]}for x in [self.lab().get_node_by_id('n91'), self.lab().get_node_by_id('n92')]]
        self.r_vtc_ncs_cli(command=tmpl_switches.render(switches=switches, domain_group='D1', bgp_asn=23))

        self.r_vtc_ncs_cli(command=sync.render(names=self.get_xrvr_names() + ['n91', 'n92']))

    def r_vtc_delete_openstack_objects(self, is_via_ncs=True):
        if is_via_ncs:
            self.r_vtc_ncs_cli('delete openstack port\ndelete openstack subnet\ndelete openstack network')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/resource-pools/vni-pool
            return NotImplemented

    def r_vtc_ncs_cli(self, command):
        self.exe('ncs_cli << EOF\nconfigure\n{}\ncommit\nexit\nexit\nEOF'.format(command))

    @decorators.section('Getting VTS version')
    def r_vtc_get_version(self):
        return self.exe('version_info')

    def r_vtc_show_tech_support(self):
        wild_card = 'VTS*tar.bz2'
        self.exe('show_tech_support')
        ans = self.exe('ls ' + wild_card)
        self._server.r_get_file_from_dir(file_name=ans, local_path='artifacts')
        self.exe('rm -r ' + wild_card)

    def r_is_xrvr_registered(self):
        try:
            xrvrs = self.r_vtc_get_xrvrs()
            if not xrvrs:
                return False
            body = self.r_collect_logs(regex='ERROR')
            names_in_body = map(lambda x: 'POST /api/running/devices/device/{}/vts-sync-xrvr/_operations/sync HTTP'.format(x.get_id()) in body, xrvrs)
            return all(names_in_body)
        except RuntimeError:
            return False

    @staticmethod
    def test_vts_sanity():
        from fabric.api import local

        local('python -m unittest lab.vts_classes.test_vts.sanity')

    def r_vtc_all(self):
        for method_name in dir(self):
            if method_name.startswith('r_vtc') and method_name != 'r_vtc_all':
                method = getattr(self, method_name)
                method()

    def r_vtc_crm_status(self):
        return self.exe('sudo crm status')

    def r_vtc_show_configuration_xrvr_groups(self, is_via_ncs=False):  #
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow configuration cisco-vts xrvr-groups xrvr-group\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888//api/running/cisco-vts/xrvr-groups/xrvr-group
            return self._rest_api('GET /api/running/cisco-vts/xrvr-groups/xrvr-group/', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_ha_cluster_members(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow ha-cluster members\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/operational/ha-cluster/members
            return self._rest_api(resource='GET /api/operational/ha-cluster/members', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_openstack_network(self, is_via_ncs=False, network_id=''):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow openstack network {}\nexit\nEOF'.format(network_id))
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://11.11.11.150:8888/api/running/openstack/network
            r = self._rest_api(resource='GET /api/running/openstack/network/{}'.format(network_id), headers={'Accept': 'application/vnd.yang.{}+json'.format('data' if network_id else 'collection')})
            return r['collection']['cisco-vts-openstack:network'] if 'collection' in r else []

    def r_vtc_show_openstack_subnet(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow openstack subnet\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/openstack/subnet
            return self._rest_api(resource='GET /api/running/openstack/subnet', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_openstack_port(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow openstack port\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/openstack/port
            return self._rest_api(resource='GET /api/running/openstack/port', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_vni_pool(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow vni-allocator pool\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://11.11.11.150:8888/api/running/resource-pools/vni-pool
            return self._rest_api(resource='GET /api/running/resource-pools/vni-pool', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_vlan_pool(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow vlan-allocator pool\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://11.11.11.150:8888/api/running/resource-pools/vni-pool
            return self._rest_api(resource='GET /api/running/resource-pools/vlan-pool', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_uuid_servers(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow configuration cisco-vts uuid-servers\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://11.11.11.150:8888/api/running/cisco-vts/uuid-servers/uuid-server
            res = self._rest_api('GET /api/running/cisco-vts/uuid-servers/uuid-server', headers={'Accept': 'application/vnd.yang.collection+json'})
            return res['collection']['cisco-vts:uuid-server']

    def r_vtc_show_devices_device(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow devices device\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/devices/device
            return self._rest_api(resource='GET /api/running/devices/device', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_set_port_for_border_leaf(self):
        import uuid
        import json

        mgmt_srv = [x for x in self.r_vtc_show_uuid_servers() if 'baremetal' in x['server-type']][0]
        tenant = 'admin'

        for network in self.r_vtc_show_openstack_network():
            port_id = str(uuid.uuid4())
            mac = 'unknown-' + str(uuid.uuid4())
            body = {"port": {"id": port_id, "status": "cisco-vts-identities:active", "tagging": "mandatory", "network-id": network['id'], "binding-host-id": mgmt_srv['server-id'],
                    "device-id": 'null', "connid": [{"id": mgmt_srv['connid']}], "admin-state-up": "true", "type": "cisco-vts-identities:baremetal", "mac-address": mac, "vlan-id": 'null'}}

            self._rest_api(resource='PATCH /api/running/cisco-vts/tenants/tenant/{0}/topologies/topology/{0}/ports/port'.format(tenant), data=json.dumps(body),
                           headers={'Content-type': 'application/vnd.yang.data+json', 'Accept': 'application/vnd.yang.collection+json'})

        # return self.exe('ncs_cli << EOF\nconfigure\nset cisco-vts tenants tenant admin ports port <port UUID> followed by body\nexit\nEOF')

    def r_vtc_old_set_port_for_border_leaf(self):
        import json
        import requests

        s = requests.Session()
        s.post('https://{}:{}/VTS/j_spring_security_check'.format(self._vip_a, 8443), data={'j_username': self._oob_username, 'j_password': self._oob_password, 'Submit': 'Login'}, verify=False)
        resp = s.get('https://{}:{}/VTS/JavaScriptServlet'.format(self._vip_a, 8443), verify=False)
        owasp_csrftoken = resp.text.rsplit('OWASP_CSRFTOKEN",', 1)[-1].split(',', 1)[0].replace('"', '').strip()

        mgmt_srv = [x for x in self.r_vtc_show_uuid_servers() if 'baremetal' in x['server-type']][0]

        for network in self.r_vtc_show_openstack_network():
            port = {'resource': {'id': network['id'],
                                 'network': {'network_name': network['name'], 'router-external': False},
                                 # 'tenant_id': tenant['vmm-tenant-id'], 'tenant_name': 'admin',
                                 'tor_port': [{'binding_host_id': mgmt_srv['server-id'], 'connid': [{'id': mgmt_srv['connid']}], 'device_id': mgmt_srv['torname'], 'mac': "", 'tagging': 'mandatory', 'type': "baremetal"}],
                                 # 'ToRPortToDelete': []
                                 }
                    }

            headers = {'Accept': 'application/json, text/plain, */*', 'Accept-Encoding': 'gzip, deflate, sdch, br', 'Content-Type': 'application/json;charset=UTF-8', 'OWASP_CSRFTOKEN': owasp_csrftoken,
                       'X-Requested-With': 'OWASP CSRFGuard Project'}
            resp = s.put('https://{}:{}/VTS/rs/vtsService/tenantTopology/admin/admin/network/{}'.format(self._vip_a, 8443, network['id']), data=json.dumps(port), headers=headers, verify=False)
            if resp.status_code != 200:
                raise RuntimeError('Failed to add {} port to {} network, reason: {}'.format(mgmt_srv['server-id'], network['name'], resp.text))
            self.log('Added {} port to {} network'.format(mgmt_srv['server-id'], network['name']))
        s.close()

    def r_vtc_validate(self):
        self.r_vtc_show_configuration_xrvr_groups()

    def r_xrvr_show_evpn(self):
        return map(lambda xrvr: xrvr.r_xrvr_show_evpn(), self.lab().get_xrvr())


class VtsHost(CimcServer):  # this class is needed just to make sure that the node is VTS host, no additional functionality to CimcServer
    ROLE = 'vts-host-n9'