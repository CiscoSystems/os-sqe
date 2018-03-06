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
        'post_sync_from':        {'rest': '-XPOST https://{ip}:8888//api/running/devices/device/{uuid}/_operations/sync-from',                                       'cli': ''},


        'put_server':            {'rest': "-XPUT -H 'Content-Type: application/vnd.yang.data+json' https://{ip}:8888/api/running/cisco-vts/uuid-servers/uuid-server/{uuid} -d '{data}'"},
        'patch_device_port':     {'rest': "-XPATCH -H 'Content-Type: application/vnd.yang.data+json' https://{ip}:8888/api/running/cisco-vts/devices/device/{uuid}/ports -d '{data}'",
                                  'json': '{"cisco-vts:ports": {"port": [{"name": "PORT", "connection-type": "cisco-vts-identities:server", "servers": {"server": [{"name": "NAME", "type": "cisco-vts-identities:baremetal", "interface-name": "eth0", "ip": "1.1.1.1"}]}}]}}'
                                 }
    }

    short = 'V'
    # https://www.cisco.com/c/dam/en/us/td/docs/net_mgmt/virtual_topology_system/2_5_2/api/Cisco_VTS_2_5_2_API_Doc.pdf
    def api_vtc_ha(self):
        # show configuration vtc-ha
        cmd = '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/vtc-ha?deep'
        return self.cmd(cmd)

    def api_openstack(self):
        # show configuration openstack vmm
        from lab.cloud.cloud_network import CloudNetwork
        from lab.cloud.cloud_subnet import CloudSubnet

        cmd = '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/openstack?deep'
        a = self.cmd(cmd)['cisco-vts-openstack:openstack']['vmm'][0]

        nets = [CloudNetwork(cloud=None, dic=x) for x in a.get('network', [])]
        subnets = [CloudSubnet(cloud=None, dic=x) for x in a.get('subnet', [])]
        for net, sub in zip(nets, subnets):
            net.subnets.append(sub)
        servers = a.get('servers', [])
        return nets, servers

    def api_pool_lst(self):
        # show configuration resource-pools
        cmd = '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/resource-pools?deep'
        return self.cmd(cmd)

    def api_port_put(self, vlan, netid, hostid, connid):
        import uuid
        import json

        portid = str(uuid.uuid4())
        dic = {'port': {'id': portid,
                        'status': 'cisco-vts-identities:active',
                        'tagging': vlan,
                        'network-id': netid,
                        'binding-host-id': hostid,
                        'connid': [{'id': connid}],
                        'admin-state-up': True,
                        'type': 'cisco-vts-identities:baremetal',
                        'mac-address': 'unknown-' + str(uuid.uuid4())
                        }
               }
        cmd = "-XPUT -H 'Content-Type: application/vnd.yang.data+json' https://{ip}:8888/api/running/cisco-vts/tenants/tenant/admin/topologies/topology/admin/ports/port/" + portid + " -d '" + json.dumps(dic) + "'"  # page29
        return self.cmd(cmd)

    def api_dev_lst(self):
        # show configuration cisco-vts devices device
        cmd = '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/cisco-vts/devices?deep'
        return self.cmd(cmd)

    def api_port_get(self, uuid):
        return self.cmd('-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/cisco-vts/tenants/tenant/admin/topologies/topology/admin/ports/port/' + uuid)

    def api_port_lst(self):
        cmd = '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/cisco-vts/tenants/tenant/admin/topologies/topology/admin/ports/port/'  # page 30
        return self.cmd(cmd)

    def api_port_del(self, uuid):
        self.cmd('-XDELETE https://{ip}:8888/api/running/cisco-vts/tenants/tenant/admin/topologies/topology/admin/ports/port/' + uuid)

    def api_srv_lst(self):
        # show configuration cisco-vts uuid-servers
        cmd = '-XGET -H "Accept: application/vnd.yang.data+json" https://{ip}:8888/api/running/cisco-vts/uuid-servers?deep'
        return self.cmd(cmd)['cisco-vts:uuid-servers']['uuid-server']

    def __init__(self, pod, dic):
        super(Vtc, self).__init__(pod=pod, dic=dic)
        self.vtc_username = dic['vtc-username']
        self.vtc_password = dic['vtc-password']

    def cmd(self, cmd):
        import json
        import time

        cmd = 'curl -s -k -u {u}:{p} '.format(u=self.vtc_username, p=self.vtc_password) + cmd.replace('{ip}', self.ip)
        for i in range(10):
            try:
                ans = self.exe(cmd, is_warn_only=True)
                if ans.failed:
                    raise RuntimeError(ans)
                else:
                    try:  # sometimes the answer is not fully formed (usually happens with server list), simply repeat
                        return json.loads(ans) if ans else {}  # it might be empty
                    except ValueError:  # something like ValueError: Unterminated string starting at: line 65 column 11 (char 4086)
                        continue
            except:  # might happen when corosync switches to new master
                time.sleep(1)
                continue
        else:
            raise RuntimeError('Failed after 10 attempts: ' + cmd)

    def show_vxlan_tunnel(self):
        return map(lambda vtf: vtf.show_vxlan_tunnel(), self.pod.get_vft())

    def get_config_and_net_part_bodies(self):
        from lab import with_config

        cfg_tmpl = with_config.read_config_from_file(cfg_path='vtc-vm-config.txt', folder='vts', is_as_string=True)
        net_part_tmpl = with_config.read_config_from_file(cfg_path='vtc-net-part-of-libvirt-domain.template', folder='vts', is_as_string=True)

        dns_ip, ntp_ip = self.pod.get_dns()[0], self.pod.get_ntp()[0]
        hostname = '{id}-{lab}'.format(lab=self.pod, id=self.id)

        a_nic = self.nics_dic('a')  # Vtc sits on out-of-tor network marked is_ssh
        a_ip, a_net_mask = a_nic.get_ip_and_mask()
        a_gw = a_nic.get_net().get_gw()

        mx_nic = self.nics_dic('mx')  # also sits on mx network
        mx_ip, mx_net_mask = mx_nic.get_ip_and_mask()
        mx_vlan = mx_nic.get_net().get_vlan_id()

        cfg_body = cfg_tmpl.format(vtc_a_ip=a_ip, a_net_mask=a_net_mask, a_gw=a_gw, vtc_mx_ip=mx_ip, mx_net_mask=mx_net_mask, dns_ip=dns_ip, ntp_ip=ntp_ip, username=self.username, password=self.password, hostname=hostname)
        net_part = net_part_tmpl.format(a_nic_name='a', mx_nic_name='mx', mx_vlan=mx_vlan)

        with with_config.WithConfig.open_artifact(hostname, 'w') as f:
            f.write(cfg_body)
        return cfg_body, net_part

    def get_cluster_conf_body(self):
        from lab import with_config

        vip_a, vip_mx = self.ip
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
        for cmd in [self.log_grep_cmd(log_files='/opt/vts/log/nso/', regex=regex), self.log_grep_cmd(log_files='/opt/vts/log/nso/localhost\:8888.access', regex='HTTP/1.1" 40')]:
            ans = self.exe(cmd, is_warn_only=True)
            body += self.single_cmd_output(cmd=cmd, ans=ans)
        return body

    def r_vtc_ncs_cli(self, command):
        self.exe('ncs_cli << EOF\nconfigure\n{}\ncommit\nexit\nexit\nEOF'.format(command))

    def r_vtc_get_version(self):
        version = self.exe('/opt/vts/bin/version_info')
        self.log(version.split('\r\n')[0])
        return version

    def r_vtc_show_tech_support(self):
        wild_card = 'VTS*tar.bz2'
        self.exe('show_tech_support')
        ans = self.exe('ls ' + wild_card)
        self.r_get_file_from_dir(rem_rel_path=ans, loc_abs_path='artifacts/vst_tech_support.bz2')
        self.exe('rm -r ' + wild_card)

    def r_vtc_crm_mon(self):
        import fabric.network

        try:
            ans = self.exe('sudo crm_mon -1', is_warn_only=True)
            d = {'master': None, 'slave': None, 'online': None, 'offline': None}
            for line in ans.split('\r\n'):
                if 'Online:' in line:
                    d['online'] = line.strip('Online:').strip(' []').split()
                elif 'OFFLINE:' in line:
                    d['offline'] = line.strip('OFFLINE:').strip('[] ')
                elif 'Masters:' in line:
                    d['master'] = line.strip(' Masters:').strip('[] ')
                elif 'Slaves:' in line:
                    d['slave'] = line.strip(' Slaves:').strip('[] ')
            return d
        except:  # during disruption, VTC VIP might be temporarily offline, reset paramico session and try again
            fabric.network.disconnect_all()
            return self.r_vtc_crm_mon()

    def r_vtc_create_border_leaf_port(self, os_networks):
        pools = self.api_pool_lst()
        vlan_pool = [x for x in pools['resource-allocator:resource-pools']['vlan-pool'] if x['name'].startswith('system')][0]['ranges']['range'][0]
        vlan_start, vlan_end = vlan_pool['start'], vlan_pool['end']

        vlan = (vlan_start + vlan_end) / 2
        srvs = self.api_srv_lst()
        connids = [srv['connid'] for srv in srvs if srv['server-id'] == 'vmtp']

        r = []
        for network in os_networks:
            for connid in connids:
                r.append(self.api_port_put(vlan=vlan, netid=network.net_id, hostid='vmtp', connid=connid))
        pass

    def r_vtc_setup(self):
        servers = self.api_srv_lst()
        for dic in self.pod.setup_data_dic['TORSWITCHINFO']['SWITCHDETAILS']:
            tor_port = dic['br_mgmt_port_info']
            tor_name = dic['hostname']
            if not [s for s in servers if tor_name in s['torname'] and tor_port in s['portname']]:
                self.pod.vtc.r_vtc_add_host_to_inventory(server_name='vmtp', tor_name=tor_name, tor_port=tor_port)


class VtcIndividual(LibVirtServer):
    def cmd(self, cmd):
        pass
