from lab.cimc import CimcServer
from lab.server import Server
from lab.vts_classes.xrvr import Xrvr
from lab.vts_classes.vtf import Vtf


class Vtc(Server):
    def _rest_api(self, resource, params=None):
        import requests
        import json
        from lab.logger import lab_logger

        from requests.packages import urllib3

        urllib3.disable_warnings()  # Suppressing warning due to self-signed certificate

        resource = resource.strip('/')
        ip, username, password = self.get_oob()
        url = 'https://{ip}:{port}/{resource}'.format(ip=ip, port=8888, resource=resource)
        auth = (username, password)
        headers = {'Accept': 'application/vnd.yang.data+json'}

        # noinspection PyBroadException
        try:
            res = requests.get(url, auth=auth, headers=headers, params=params, timeout=100, verify=False)
            return json.loads(res.text)
        except:
            lab_logger.exception('Url={url} auth={auth},vtc headers={headers}, param={params}'.format(url=url, auth=auth, headers=headers, params=params))

    def cmd(self, cmd, **kwargs):
        return self._rest_api(resource=cmd)

    def get_vni_pool(self):
        ans = self._rest_api(resource='/api/running/resource-pools/vni-pool/vnipool')
        return ans

    def get_vtf(self, compute_hostname):
        for vtf in self.lab().get_nodes_by_class(Vtf):
            n = vtf.get_compute_node()
            if n.actuate_hostname(refresh=False) == compute_hostname:
                return vtf

    def check_vtfs(self):
        self.check_or_install_packages('sshpass')
        ans = self._rest_api(resource='/api/running/cisco-vts')
        vtf_ips_from_vtc = [x['ip'] for x in ans['cisco-vts:cisco-vts']['vtfs']['vtf']]
        vtf_nodes = self.lab().get_nodes_by_class(Vtf)
        for vtf in vtf_nodes:
            ip, _, _, _ = vtf.get_ssh()
            if str(ip) not in vtf_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(vtf, self))
            vtf.actuate()
        return vtf_nodes

    def check_xrvr(self):
        xrvr_nodes = self.lab().get_nodes_by_class(Xrvr)
        items = self.json_api_get_network_inventory()['items']
        xrvr_ips_from_vtc = [x['ip_address'] for x in items if 'ASR9K' == x['devicePlaform'] and 'xrvr' in x['id'].lower()]
        for xrvr in xrvr_nodes:
            ip, _, _, _ = xrvr.get_ssh()
            if str(ip) not in xrvr_ips_from_vtc:
                raise RuntimeError('{0} is not detected by {1}'.format(xrvr, self))
            xrvr.actuate()
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

    def json_api_get_network_inventory(self):
        return self.json_api_get('rs/ncs/query/networkInventory')

    def restart_dl_server(self):
        return map(lambda xrvr: xrvr.restart_dl_server(), self.lab().get_nodes_by_class(Xrvr))

    def show_evpn(self):
        return map(lambda xrvr: xrvr.show_evpn(), self.lab().get_nodes_by_class(Xrvr))

    def show_connections_xrvr_vtf(self):
        return map(lambda vtf: vtf.show_connections_xrvr_vtf(), self.lab().get_nodes_by_class(Vtf)) + map(lambda xrvr: xrvr.show_connections_xrvr_vtf(), self.lab().get_nodes_by_class(Xrvr))

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.lab().get_nodes_by_class(Vtf))

    def show_logs(self, what='error'):
        self.run('grep -i {0} /var/log/ncs/*'.format(what), warn_only=True)

    def show_uuid_servers(self):
        pass  # ncs_cli -u admin show configuration cisco-vts uuid-servers

    def disrupt(self, start_or_stop):
        pass  # TODO: implement actual disruptor when devs ready

    def actuate(self):
        self.check_xrvr()
        self.check_vtfs()

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

        cfg_tmpl = with_config.read_config_from_file(config_path='vtc_vm_config.txt', directory='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(config_path='vtc-net-part-of-libvirt-domain.template', directory='vts', is_as_string=True)

        dns_ip, ntp_ip = self.lab().get_dns()[0], self.lab().get_ntp()[0]
        lab_name = str(self.lab())

        _, ssh_username, ssh_password = self.get_ssh()

        nic_ssh_net = filter(lambda x: x.is_ssh(), self.get_nics().values())[0]  # Vtc sits on out-of-tor network marked is_ssh
        ssh_ip, ssh_netmask = nic_ssh_net.get_ip_and_mask()
        ssh_gw = nic_ssh_net.get_net()[1]

        nic_vts_net = filter(lambda x: x.is_vts(), self.get_nics().values())[0]  # also sits on  local network marked is_vts
        loc_ip, loc_netmask = nic_vts_net.get_ip_and_mask()
        vlan = nic_vts_net.get_net().get_vlan()

        cfg_body = cfg_tmpl.format(ssh_ip=ssh_ip, ssh_netmask=ssh_netmask, ssh_gw=ssh_gw, loc_ip=loc_ip, loc_netmask=loc_netmask, dns_ip=dns_ip, ntp_ip=ntp_ip, username=ssh_username, password=ssh_password,
                                   lab_name=lab_name)
        net_part = net_part_tmpl.format(vlan=vlan)

        return cfg_body, net_part


class VtsHost(CimcServer):  # this class is needed just to make sure that the node is VTS host, no additional functionality to CimcServer
    pass
