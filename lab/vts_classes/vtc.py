from lab.cimc import CimcServer
from lab.nodes.lab_server import LabServer
from lab.vts_classes.vtf import Vtf
from lab.vts_classes.xrvr import Xrvr


class Vtc(LabServer):
    ROLE = 'vtc'

    def __init__(self, node_id, role, lab):
        super(Vtc, self).__init__(node_id=node_id, role=role, lab=lab)
        self._vip_a, self._vip_mx = 'Default in Vtc.__init()', 'Default in Vtc.__init()'
        self._is_api_via_vip = True

    def __repr__(self):
        oob_ip, oob_u, oob_p = self.get_oob()
        return u'{l} {n} | {s} https://{ip} with {u}/{p}'.format(l=self.lab(), n=self.get_id(), s=self._server, ip=self.get_vtc_vips()[0], p=oob_p, u=oob_u)

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

        # noinspection PyBroadException
        try:
            if type_of_call in ['get', 'GET']:
                ans = requests.get(url, auth=auth, headers=headers, params=params, timeout=100, verify=False)
            elif type_of_call in ['patch', 'PATCH']:
                ans = requests.patch(url, auth=auth, headers=headers, data=data, timeout=100, verify=False)
            else:
                raise ValueError('Unsupported type of call: "{}"'.format(type_of_call))
            if ans.ok:
                d = {'call': resource}
                if ans.text:
                    d.update(json.loads(ans.text))
                return d
            else:
                raise RuntimeError('for {}: {}'.format(resource, ans.text or ans.reason))
        except AttributeError:
            self.log(message='Possible methods get, post, patch', level='exception')
        except requests.ConnectTimeout:
            self.log(message='Url={url} auth={auth}, headers={headers}, param={params}'.format(url=url, auth=auth, headers=headers, params=params), level='exception')
            raise

    def set_vip(self, vip):
        self._vip_a, self._vip_mx = vip, '11.11.11.150'

    def get_vtc_vips(self):
        return self._vip_a, self._vip_mx

    def cmd(self, cmd, **kwargs):
        return self._rest_api(resource=cmd, headers={})

    def get_vtf(self, compute_hostname):
        for vtf in self.lab().get_nodes_by_class(Vtf):
            n = vtf.get_compute_node()
            if n.actuate_hostname(refresh=False) == compute_hostname:
                return vtf

    def get_xrvr_names(self):
        return map(lambda x: x.get_id(), self.get_xrvrs())

    def get_xrvrs(self):
        return self.lab().get_nodes_by_class(Xrvr)

    def r_vtc_get_vtfs(self):
        ans = self._rest_api(resource='GET /api/running/cisco-vts', headers={'Accept': 'application/vnd.yang.data+json'})
        vtf_ips_from_vtc = [x['ip'] for x in ans['cisco-vts:cisco-vts']['vtfs']['vtf']]
        vtf_nodes = self.lab().get_nodes_by_class(Vtf)
        for vtf in vtf_nodes:
            _, username, password = vtf.get_oob()
            vtf.set_oob_creds(ip=vtf_ips_from_vtc.pop(0), username=username, password=password)
        return vtf_nodes

    def r_vtc_get_xrvrs(self):
        xrvr_nodes = self.lab().get_nodes_by_class(Xrvr)
        devices = self.r_vtc_show_devices_device()
        if 'collection' not in devices:
            return []
        xrvr_ips_from_vtc = [x['address'] for x in devices['collection']['tailf-ncs:device']]
        for xrvr in xrvr_nodes:
            if str(xrvr.get_ip_mx()) not in xrvr_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(xrvr, self))
        return xrvr_nodes

    def json_api_url(self, resource):
        import os
        url = 'https://{ip}:{port}/VTS'.format(ip=self._oob_ip, port=8443)
        return os.path.join(url, resource)

    def json_api_session(self):
        import requests

        s = requests.Session()
        auth = s.post(self.json_api_url('j_spring_security_check'), data={'j_username': self._oob_username, 'j_password': self._oob_password, 'Submit': 'Login'}, verify=False)
        if 'Invalid username or passphrase' in auth.text:
            raise Exception('Invalid username or passphrase')

        return s

    def json_api_get(self, resource):
        s = None
        r = {'items': []}
        try:
            s = self.json_api_session()
            response = s.get(self.json_api_url(resource))
            if response.status_code == 200:
                r = response.json()
        except Exception as e:
            raise e
        finally:
            s.close()
        return r

    def xrvr_restart_dl(self):
        return map(lambda xrvr: xrvr.xrvr_restart_dl(), self.lab().get_nodes_by_class(Xrvr))

    def show_connections_xrvr_vtf(self):
        return map(lambda vtf: vtf.show_connections_xrvr_vtf(), self.lab().get_nodes_by_class(Vtf)) + map(lambda xrvr: xrvr.xrvr_show_connections_xrvr_vtf(), self.lab().get_nodes_by_class(Xrvr))

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.lab().get_nodes_by_class(Vtf))

    def disrupt(self, start_or_stop, method_to_disrupt):
        vts_host = [x.get_peer_node(self) for x in self.get_all_wires() if x.get_peer_node(self).is_vts_host()][0]

        if method_to_disrupt == 'vm-shutdown':
            ans = vts_host.exe('virsh list | grep vtc')
            vm_name = ans.split()[1]
            vts_host.exe(command='virsh {} {}'.format('suspend' if start_or_stop == 'start' else 'resume', vm_name))
        elif method_to_disrupt == 'isolate-from-mx':
            ans = vts_host.exe('ip l | grep mgmt | grep vtc')
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} {}'.format(if_name, 'down' if start_or_stop == 'start' else 'up'))
        elif method_to_disrupt == 'isolate-from-api':
            ans = vts_host.exe('ip l | grep api | grep vtc')
            if_name = ans.split()[1][:-1]
            vts_host.exe('ip l s dev {} {}'.format(if_name, 'down' if start_or_stop == 'start' else 'up'))
        elif method_to_disrupt == 'vm-reboot' and start_or_stop == 'start':
            self.exe('sudo shutdown -r now')

    def get_overlay_networks(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesNetworkAll?limit=2147483647&name=' + name)

    def get_overlay_network(self, network_id):
        networks = self.get_overlay_networks()
        for network in networks['items']:
            if network_id == network['id']:
                return network

    def get_overlay_network_subnets(self, network_id, topology_id='admin', name='admin'):
        resource = 'rs/ncs/query/networkSubnetInfoPopover?' \
                   'limit=2147483647&name={n}&network-id={net_id}&topologyId={t}'.format(net_id=network_id,
                                                                                         t=topology_id,
                                                                                         n=name)
        return self.json_api_get(resource)

    def get_overlay_network_ports(self, network_id):
        resource = 'rs/vtsService/tenantTopology/admin/admin/ports?network-Id={0}'.format(network_id)
        return self.json_api_get(resource)

    def get_overlay_network_port(self, network_id, port_id):
        ports = self.get_overlay_network_ports(network_id)
        for port in ports['items']:
            if port_id == port['id']:
                return port

    def get_overlay_routers(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesRouterAll?limit=2147483647&name=' + name)

    def get_verlay_virtual_machines(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesRouterAll?limit=2147483647&name=' + name)

    def get_overlay_devices(self):
        return self.json_api_get('rs/ncs/query/devices?limit=2147483647')

    def get_overlay_vms(self, name='admin'):
        return self.json_api_get('rs/ncs/query/tenantPortsAll?limit=2147483647&name=' + name)

    def get_overlay_device_vlan_vni_mapping(self, device_name):
        resource = 'rs/ncs/operational/vlan-vni-mapping/{0}'.format(device_name)
        return self.json_api_get(resource)

    def verify_network(self, os_network):
        overlay_network = self.get_overlay_network(os_network['id'])
        net_flag = False
        if overlay_network:
            net_flag = True
            net_flag &= overlay_network['name'] == os_network['name']
            net_flag &= overlay_network['status'] == os_network['status'].lower()
            net_flag &= overlay_network['admin-state-up'] == os_network['admin_state_up'].lower()
            net_flag &= overlay_network['provider-network-type'] == os_network['provider:network_type']
            net_flag &= overlay_network['provider-physical-network'] == os_network['provider:physical_network']
            net_flag &= overlay_network['provider-segmentation-id'] == os_network['provider:segmentation_id']
            net_flag &= overlay_network['provider-segmentation-id'] == os_network['provider:segmentation_id']
        return net_flag

    def verify_subnet(self, os_network_id, os_subnet):
        overlay_subnet = self.get_overlay_network_subnets(os_network_id)['items']
        subnet_synced = len(overlay_subnet) > 0
        if subnet_synced:
            overlay_subnet = overlay_subnet[0]
            subnet_synced &= overlay_subnet['cidr'] == os_subnet['cidr']
            subnet_synced &= overlay_subnet['enable-dhcp'] == os_subnet['enable_dhcp'].lower()
            subnet_synced &= overlay_subnet['gateway-ip'] == os_subnet['gateway_ip']
            subnet_synced &= overlay_subnet['id'] == os_subnet['id']
            subnet_synced &= overlay_subnet['ip-version'] == os_subnet['ip_version']
            subnet_synced &= overlay_subnet['name'] == os_subnet['name']
            subnet_synced &= overlay_subnet['network-id'] == os_subnet['network_id']
        return subnet_synced

    def verify_ports(self, os_network_id, os_ports):
        overlay_ports = self.get_overlay_network_ports(network_id=os_network_id)['items']
        ports_synced = len(overlay_ports) == len(os_ports)
        if ports_synced:
            for port in os_ports:
                try:
                    overlay_port = next(p for p in overlay_ports if p['id'] == port['id'])
                    ports_synced &= overlay_port['mac'] == port['mac_address']
                except StopIteration:
                    ports_synced = False
                    break
        return ports_synced

    def verify_instances(self, os_instances):
        vms = self.get_overlay_vms()['items']
        instances_synced = len(vms) == len(os_instances)
        return instances_synced

    def get_config_and_net_part_bodies(self):
        from lab import with_config

        cfg_tmpl = with_config.read_config_from_file(config_path='vtc-vm-config.txt', directory='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(config_path='vtc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        dns_ip, ntp_ip = self.lab().get_dns()[0], self.lab().get_ntp()[0]
        hostname = '{id}-{lab}'.format(lab=self.lab(), id=self.get_id())

        _, ssh_username, ssh_password = self._server.get_ssh()

        a_nic = self.get_nic('a')  # Vtc sits on out-of-tor network marked is_ssh
        a_ip, a_net_mask = a_nic.get_ip_and_mask()
        a_gw = a_nic.get_net().get_gw()

        mx_nic = self.get_nic('mx')  # also sits on mx network
        mx_ip, mx_net_mask = mx_nic.get_ip_and_mask()
        mx_vlan = mx_nic.get_net().get_vlan()

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
        if not owasp_csrftoken:
            raise RuntimeError('OWASP_CSRFTOKEN token has not been found in: ' + java_script_servlet.text)

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
        cluster = None
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

        map(lambda y: y.r_xrvr_day0_config(), self.get_xrvrs())
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
            return self._rest_api(resource='GET /api/running/openstack/network/{}'.format(network_id), headers={'Accept': 'application/vnd.yang.{}+json'.format('data' if network_id else 'collection')})

    def r_vtc_get_openstack_network_vlan(self, network_id):
        a = self.r_vtc_show_openstack_network(network_id=network_id)
        return a['cisco-vts-openstack:network']['provider-segmentation-id']

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
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/resource-pools/vni-pool
            return self._rest_api(resource='GET /api/running/resource-pools/vni-pool', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_show_uuid_servers(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow configuration cisco-vts uuid-servers\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/cisco-vts/uuid-servers
            return self._rest_api('GET /api/running/cisco-vts/uuid-servers', headers={'Accept': 'application/vnd.yang.data+json'})

    def r_vtc_show_devices_device(self, is_via_ncs=False):
        if is_via_ncs:
            return self.exe('ncs_cli << EOF\nshow devices device\nexit\nEOF')
        else:
            # curl -v -k -X GET -u admin:Cisco123! https://111.111.111.150:8888/api/running/devices/device
            return self._rest_api(resource='GET /api/running/devices/device', headers={'Accept': 'application/vnd.yang.collection+json'})

    def r_vtc_validate(self):
        self.r_vtc_show_configuration_xrvr_groups()

    def r_xrvr_show_evpn(self):
        return map(lambda xrvr: xrvr.r_xrvr_show_evpn(), self.lab().get_nodes_by_class(Xrvr))


class VtsHost(CimcServer):  # this class is needed just to make sure that the node is VTS host, no additional functionality to CimcServer
    ROLE = 'vts-host-n9'
