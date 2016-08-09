from lab.cimc import CimcServer
from lab.server import Server
from lab.vts_classes.xrvr import Xrvr
from lab.vts_classes.vtf import Vtf


class Vtc(Server):
    ROLE = 'vtc'

    def __init__(self, node_id, role, lab, hostname):
        super(Server, self).__init__(node_id=node_id, role=role, lab=lab, hostname=hostname)
        self._vip_a, self._vip_mx = 'Default in Vtc.__init()', 'Default in Vtc.__init()'
        self._is_api_via_vip = True

    def form_mac(self, net_octet_in_mac):
        return '00:{lab:02}:A0:F0:{count:02}:{net}'.format(lab=self._lab.get_id(), count=self._n, net=net_octet_in_mac)

    def __repr__(self):
        ssh_ip, ssh_u, ssh_p = self.get_ssh()
        oob_ip, oob_u, oob_p = self.get_oob()
        return u'{l} {n} | sshpass -p {p1} ssh {u1}@{ip1}  https://{ip1} with {u2}/{p2}'.format(l=self.lab(), n=self.get_id(), ip1=ssh_ip, p1=ssh_p, u1=ssh_u, ip2=oob_ip, p2=oob_p, u2=oob_u)

    def disable_vip(self):
        self._is_api_via_vip = False

    def _rest_api(self, resource, data=None, params=None, type_of_call='get'):
        import requests
        import json

        # from requests.packages import urllib3

        # urllib3.disable_warnings()  # Suppressing warning due to self-signed certificate

        resource = resource.strip('/')
        _, username, password = self.get_oob()
        vip = self.get_vtc_vips()[0] if self._is_api_via_vip else self.get_ssh_ip()
        url = 'https://{ip}:{port}/{resource}'.format(ip=vip, port=8888, resource=resource)
        auth = (username, password)
        headers = {'Accept': 'application/vnd.yang.data+json' if 'cisco' in resource else 'application/vnd.yang.collection+json'}

        # noinspection PyBroadException
        try:
            if type_of_call == 'get':
                ans = requests.get(url, auth=auth, headers=headers, params=params, timeout=100, verify=False)
            elif type_of_call == 'patch':
                ans = requests.patch(url, auth=auth, headers=headers, data=data, timeout=100, verify=False)
            else:
                raise ValueError('Unsupported type of call: "{}"'.format(type_of_call))
            if ans.ok:
                d = {'call': resource}
                if ans.text:
                    d.update(json.loads(ans.text))
                return d
            else:
                self.log(message='{}'.format(ans))
                return ans
        except AttributeError:
            self.log(message='Possible methods get, post, patch', level='exception')
        except requests.ConnectTimeout:
            self.log(message='Url={url} auth={auth}, headers={headers}, param={params}'.format(url=url, auth=auth, headers=headers, params=params), level='exception')
            raise

    def vtc_get_call(self, resource, params=None):
        return self._rest_api(resource=resource, params=params, type_of_call='get')

    def vtc_patch_call(self, resource, data):
        return self._rest_api(resource=resource, data=data, type_of_call='patch')

    def set_vip(self, vip):
        self._vip_a, self._vip_mx = vip, '111.111.111.150'

    def get_vtc_vips(self):
        return self._vip_a, self._vip_mx

    def cmd(self, cmd, **kwargs):
        return self._rest_api(resource=cmd)

    def vtc_get_vni_pool(self):
        ans = self.vtc_get_call(resource='/api/running/resource-pools/vni-pool/vnipool')
        return ans

    def get_vtf(self, compute_hostname):
        for vtf in self.lab().get_nodes_by_class(Vtf):
            n = vtf.get_compute_node()
            if n.actuate_hostname(refresh=False) == compute_hostname:
                return vtf

    def vtc_get_vtfs(self):
        vtf_host_last = self.lab().get_nodes_by_class(VtsHost)[-1]
        ans = self.vtc_get_call(resource='/api/running/cisco-vts')
        vtf_ips_from_vtc = [x['ip'] for x in ans['cisco-vts:cisco-vts']['vtfs']['vtf']]
        vtf_nodes = self.lab().get_nodes_by_class(Vtf)
        for vtf in vtf_nodes:
            _, username, password = vtf.get_oob()
            vtf.set_oob_creds(ip=vtf_ips_from_vtc.pop(0), username=username, password=password)
            vtf.set_proxy(proxy=vtf_host_last)
        return vtf_nodes

    def vtc_get_net_inventory(self):
        ans = self.vtc_get_call(resource='/api/running/cisco-vts/devices')
        return ans

    def vtc_get_xrvrs(self):
        xrvr_nodes = self.lab().get_nodes_by_class(Xrvr)
        devices = self.vtc_get_call(resource='/api/running/devices/device')
        xrvr_ips_from_vtc = [x['address'] for x in devices['collection']['tailf-ncs:device']]
        for xrvr in xrvr_nodes:
            ip = xrvr.get_nic('mx').get_ip_and_mask()[0]
            if str(ip) not in xrvr_ips_from_vtc:
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

    def restart_dl_server(self):
        return map(lambda xrvr: xrvr.restart_dl_server(), self.lab().get_nodes_by_class(Xrvr))

    def show_evpn(self):
        return map(lambda xrvr: xrvr.show_evpn(), self.lab().get_nodes_by_class(Xrvr))

    def show_connections_xrvr_vtf(self):
        return map(lambda vtf: vtf.show_connections_xrvr_vtf(), self.lab().get_nodes_by_class(Vtf)) + map(lambda xrvr: xrvr.show_connections_xrvr_vtf(), self.lab().get_nodes_by_class(Xrvr))

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.lab().get_nodes_by_class(Vtf))

    def disrupt(self, start_or_stop, method_to_disrupt):
        vts_host = [x.get_peer_node(self) for x in self.get_all_wires() if x.get_peer_node(self).is_vts_host()][0]
        if method_to_disrupt == 'vm-shutdown':
            vts_host.run(command='virsh {} vtc'.format('suspend' if start_or_stop == 'start' else 'resume'))
        elif method_to_disrupt == 'isolate-from-mx':
            vts_host.run('ip l s dev vtc-mx-port {}'.format('down' if start_or_stop == 'start' else 'up'))
        elif method_to_disrupt == 'isolate-from-api':
            vts_host.run('ip l s dev vtc-a-port {}'.format('down' if start_or_stop == 'start' else 'up'))

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

        _, ssh_username, ssh_password = self.get_ssh()

        a_nic = self.get_nic('a')  # Vtc sits on out-of-tor network marked is_ssh
        a_ip, a_net_mask = a_nic.get_ip_and_mask()
        a_gw = a_nic.get_net()[1]

        mx_nic = self.get_nic('mx')  # also sits on mx network
        mx_ip, mx_net_mask = mx_nic.get_ip_and_mask()
        mx_vlan = mx_nic.get_net().get_vlan()

        cfg_body = cfg_tmpl.format(vtc_a_ip=a_ip, a_net_mask=a_net_mask, a_gw=a_gw, vtc_mx_ip=mx_ip, mx_net_mask=mx_net_mask, dns_ip=dns_ip, ntp_ip=ntp_ip, username=ssh_username, password=ssh_password, hostname=hostname)
        net_part = net_part_tmpl.format(a_nic_name=a_nic.get_name(), mx_nic_name=mx_nic.get_name(), mx_vlan=mx_vlan)

        with with_config.open_artifact(hostname, 'w') as f:
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
        with with_config.open_artifact('cluster.conf', 'w') as f:
            f.write(cfg_body)
        return cfg_body

    def vtc_change_user(self):
        import json

        _, username, password = self.get_oob()
        self.set_oob_creds(ip=self.get_ssh_ip(), username='admin', password='admin')
        response = self.vtc_get_call(resource='/api/running/aaa/authentication/users/user/{}'.format('admin'))  # openssl passwd -1 -salt xxx Cisco123!
        if response.ok:
            d = json.loads(response.text)
            user = d['tailf-aaa:user']
            user.pop('operations')
            user['password'] = password
            self.vtc_patch_call(resource='/api/running/aaa/authentication/users/user', data=json.dumps({'user': user}))
        self.set_oob_creds(ip=self.get_ssh_ip(), username=username, password=password)

    def vtc_get_os_network(self):
        self.vtc_get_call(resource='/api/running/openstack/network')  # ans.text == '' or ans.txt == '????'
        ans = self.vtc_get_call(resource='/api/running/openstack/subnet')
        return ans

    def vtc_get_os_ports(self):
        return self.vtc_get_call(resource='/api/running/openstack/port')

    def vtc_get_cluster_info(self):
        d = self.vtc_get_call(resource='/api/operational/ha-cluster/members')  # curl -v -k -X GET -u <vtc-username>:<vtc-password> https://<VTC_IP>:8888/api/operational/ha-cluster/members
        return d['collection']['tcm:members']

    def vtc_ncs_show_ha_cluster(self):
        d = self.run('ncs_cli << EOF\nshow ha-cluster\nexit\nEOF')
        return d

    def vtc_ncs_show_openstack_port(self):
        d = self.run('ncs_cli << EOF\nshow openstack port\nexit\nEOF')
        return d

    def vtc_ncs_show_uuid_servers(self):
        d = self.run('ncs_cli << EOF\nshow configuration cisco-vts uuid-servers\nexit\nEOF')
        return d

    def vtc_get_vfg(self):
        d = self.vtc_get_call(resource='/api/operational/ha-cluster/members')  # curl -v -k -X GET -u <vtc-username>:<vtc-password> https://<VTC_IP>:8888/api/operational/ha-cluster/members
        return d['collection']['tcm:members']

    def check_cluster_is_formed(self):
        nodes = self.lab().get_nodes_by_class(Vtc)
        reported_ips = [x['address'] for x in self.vtc_get_cluster_info()]
        for node in nodes:
            if node.get_ssh_ip() not in reported_ips:
                return False
        return True

    def get_logs(self):
        body = ''
        for cmd in ['grep -i error /var/log/ncs/*', ' cat /var/log/ncs/localhost\:8888.access']:
            ans = self.run(cmd)
            body += self._format_single_cmd_output(cmd=cmd, ans=ans)
        return body

    def get_all_logs(self, name):
        body = ''
        for node in self.lab().get_nodes_by_class([Vtc, Xrvr]):
            body += node.get_logs()

        self.log_to_artifact_file(name='{}-vts-logs.txt'.format(name), body=body)

    def vtc_day0_config(self):  # https://cisco.jiveon.com/docs/DOC-1469629
        pass

    @staticmethod
    def test_vts_sanity():
        from fabric.api import local

        local('python -m unittest lab.vts_classes.test_vts.sanity')


class VtsHost(CimcServer):  # this class is needed just to make sure that the node is VTS host, no additional functionality to CimcServer
    ROLE = 'vts-host-n9'

    def form_mac(self, net_octet_in_mac):
        return '00:{lab:02}:A0:FF:{count:02}:{net}'.format(lab=self._lab.get_id(), count=self._n, net=net_octet_in_mac)
