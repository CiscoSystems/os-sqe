import sys


class VtcUI(object):
    def __init__(self, ui_ip, ui_user, ui_password):
        self._ui_ip = ui_ip
        self._ui_user = ui_user
        self._ui_password = ui_password
        self._session = None

    def json_api_url(self, resource):
        import os
        url = 'https://{ip}:{port}/VTS'.format(ip=self._ui_ip, port=8443)
        return os.path.join(url, resource)

    def json_api_session(self):
        import requests
        import re

        if not self._session:
            self._session = requests.Session()
            auth = self._session.post(self.json_api_url('j_spring_security_check'), data={'j_username': self._ui_user, 'j_password': self._ui_password, 'Submit': 'Login'}, verify=False)
            if 'Invalid username or passphrase' in auth.text:
                raise Exception('Invalid username or passphrase')

            url = self.json_api_url('JavaScriptServlet')
            resp_csrftoken = self._session.get(url, verify=False)
            owasp_csrftoken = ''.join(re.findall('OWASP_CSRFTOKEN", "(.*?)", requestPageTokens', resp_csrftoken.text))
            if not owasp_csrftoken:
                raise Exception('OWASP_CSRFTOKEN token has not been found')
            self._owasp_csrftoken = owasp_csrftoken

        return self._session

    def json_api_get(self, resource):
        s = None
        r = {'items': []}
        try:
            s = self.json_api_session()
            url = self.json_api_url(resource.strip('/'))
            sys.stdout.writelines('\nVTC request: {0}\n'.format(url))
            response = s.get(self.json_api_url(resource.strip('/')), verify=False)
            if response.status_code == 200:
                r = response.json()
            sys.stdout.writelines('\nVTC response: {0}\n'.format(r))
        except Exception as e:
            raise e
        finally:
            if s:
                s.close()
        return r

    def json_api_put(self, resource, data):
        s = None
        response = None
        try:
            s = self.json_api_session()
            url = self.json_api_url(resource.strip('/'))
            sys.stdout.writelines('\nVTC put request: {0}, {1}\n'.format(url, data))

            headers = {'Accept': 'application/json, text/plain, */*',
                       'Accept-Encoding': 'gzip, deflate, sdch, br',
                       'Content-Type': 'application/json;charset=UTF-8'}
            if self._owasp_csrftoken:
                headers['OWASP_CSRFTOKEN'] = self._owasp_csrftoken
                headers['X-Requested-With'] = 'OWASP CSRFGuard Project'
            response = s.put(self.json_api_url(resource.strip('/')), data=data, headers=headers, verify=False)
            sys.stdout.writelines('\nVTC r.text: {0}\n'.format(response.text))
            sys.stdout.writelines('\nVTC response: {0}\n'.format(response))
        except Exception as e:
            raise e
        finally:
            if s:
                s.close()
        return response

    def json_api_delete(self, resource):
        s = None
        response = None
        try:
            s = self.json_api_session()
            url = self.json_api_url(resource.strip('/'))
            sys.stdout.writelines('\nVTC delete request: {0}\n'.format(url))

            headers = {'Accept': 'application/json, text/plain, */*',
                       'Accept-Encoding': 'gzip, deflate, sdch, br',
                       'Content-Type': 'application/json;charset=UTF-8'}
            if self._owasp_csrftoken:
                headers['OWASP_CSRFTOKEN'] = self._owasp_csrftoken
                headers['X-Requested-With'] = 'OWASP CSRFGuard Project'
            response = s.delete(self.json_api_url(resource.strip('/')), headers=headers, verify=False)
            sys.stdout.writelines('\nVTC r.text: {0}\n'.format(response.text))
            sys.stdout.writelines('\nVTC response: {0}\n'.format(response))
        except Exception as e:
            raise e
        finally:
            if s:
                s.close()
        return response

    def get_network_inventory(self):
        return self.json_api_get('rs/ncs/query/networkInventory')['items']

    def get_network_inventory_xrvr(self):
        items = self.get_network_inventory()
        return [item for item in items if item['isxrvr'] == 'true']

    def get_overlay_networks(self, tenant_name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesNetworkAll?limit=2147483647&name=' + tenant_name)['items']

    def get_overlay_network(self, network_id, tenant_name='admin'):
        networks = self.get_overlay_networks(tenant_name)
        for network in networks:
            if network_id == network['id']:
                return network

    def get_overlay_network_subnets(self, network_id, topology_id='admin', name='admin'):
        resource = 'rs/ncs/query/networkSubnetInfoPopover?' \
                   'limit=2147483647&name={n}&network-id={net_id}&topologyId={t}'.format(net_id=network_id,
                                                                                         t=topology_id,
                                                                                         n=name)
        return self.json_api_get(resource)['items']

    def get_overlay_network_ports(self, network_id):
        resource = 'rs/vtsService/tenantTopology/admin/admin/ports?network-Id={0}'.format(network_id)
        return self.json_api_get(resource)['items']

    def get_overlay_network_port(self, network_id, port_id):
        ports = self.get_overlay_network_ports(network_id)
        for port in ports:
            if port_id == port['id']:
                return port

    def get_overlay_routers(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesRouterAll?limit=2147483647&name=' + name)

    def get_verlay_virtual_machines(self, name='admin'):
        return self.json_api_get('rs/ncs/query/topologiesRouterAll?limit=2147483647&name=' + name)

    def get_overlay_devices(self):
        return self.json_api_get('rs/ncs/query/devices?limit=2147483647')

    def get_overlay_vms(self, name='admin'):
        return self.json_api_get('rs/ncs/query/tenantPortsAll?limit=2147483647&name=' + name)['items']

    def get_overlay_vm(self, port_id, name='admin'):
        ports = self.get_overlay_vms(name)
        for p in ports:
            if p['id'] == port_id:
                return p

    def get_overlay_device_vlan_vni_mapping(self, device_name):
        resource = 'rs/ncs/operational/vlan-vni-mapping/{0}'.format(device_name)
        return self.json_api_get(resource)

    def get_virtual_forwarding_groups(self):
        resource = 'rs/vfg'
        return self.json_api_get(resource)

    def get_vni_pools(self):
        resource = 'rs/ncs/vni-pool'
        return self.json_api_get(resource)['items']

    def get_ethernet_mappings(self, device_name):
        resource = 'rs/ncs/query/ethernet-mappings?deviceNameTOR={0}&limit=2147483647'.format(device_name)
        return self.json_api_get(resource)['items']

    def get_tenants(self):
        resource = 'rs/ncs/query/tenants?limit=2147483647'
        return self.json_api_get(resource)['items']

    def get_tenant(self):
        tenants = self.get_tenants()
        for tenant in tenants:
            if self._ui_user == tenant['name']:
                return tenant

    def put_network_port(self, network_id, data):
        resource = 'rs/vtsService/tenantTopology/admin/admin/network/{0}'.format(network_id)
        return self.json_api_put(resource, data)

    def delete_network_port(self, port_id):
        resource = 'rs/vtsService/tenantTopology/admin/admin/ports/{0}'.format(port_id)
        return self.json_api_delete(resource)

    def verify_network(self, os_network):
        overlay_network = self.get_overlay_network(os_network['id'])
        net_flag = False
        if overlay_network:
            net_flag = True
            net_flag &= overlay_network['name'] == os_network['name']
            net_flag &= overlay_network['status'] == os_network['status'].lower()
            net_flag &= overlay_network['admin-state-up'] == str(os_network['admin_state_up'] == 'UP').lower()
            net_flag &= overlay_network['provider-network-type'] == os_network['provider:network_type']
            net_flag &= overlay_network['provider-physical-network'] == os_network['provider:physical_network']
            net_flag &= overlay_network['provider-segmentation-id'] == os_network['provider:segmentation_id']
        return net_flag

    def verify_subnet(self, os_network_id, os_subnet):
        overlay_subnet = self.get_overlay_network_subnets(os_network_id)
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
        overlay_ports = self.get_overlay_network_ports(network_id=os_network_id)
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

    def verify_instances(self, os_ports):
        ports_flag = True
        ports = self.get_overlay_vms()
        for os_p in os_ports:
            p = [p for p in ports if p['id'] == os_p['id']]
            ports_flag = len(p) == 1
            if not ports_flag:
                break
            p = p.pop()
            ports_flag &= p['admin-state-up'] == os_p['admin_state_up'].lower()
            ports_flag &= p['mac-address'] == os_p['mac_address']
            ports_flag &= p['network-id'] == os_p['network_id']
        return ports_flag
