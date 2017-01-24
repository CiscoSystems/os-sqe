from lab.nodes import LabNode
from lab.nodes.lab_server import LabServer


class FiServer(LabServer):
    _server_id = None
    _service_profile_name = None

    def cmd(self, cmd):
        pass

    def set_ucsm_id(self, server_port):
        a_or_b = server_port[-2:]
        if a_or_b not in ['/a', '/b']:
            raise ValueError('server_port should ends with /a or /b, while provided: {0}'.format(server_port))
        server_id = server_port[:-2]
        self._server_id = str(server_id)
        self._service_profile_name = '{l}-{bc}{i}-{n}'.format(l=self.lab(), i='-'.join(self._server_id.split('/')), n=self.get_node_id(), bc='B' if '/' in self._server_id else 'C')

    def get_ucsm_info(self):
        return self._server_id, self._service_profile_name

    def correct_port_id(self, port_id):
        left, right = port_id.rsplit('/', 1)
        if right not in ['a', 'b']:
            raise ValueError('{}: port id "{}" is wrong, it has to be ending as "/a" or "/b"'.format(self, port_id))

        for value in left.split('/'):
            try:
                int(value)
            except ValueError:
                raise ValueError('{}: port id "{}" is wrong, has to be "<number>" or "<number>/<number>" before "/a" or "/b"'.format(self, port_id))
        return port_id


class FiDirector(FiServer):
    ROLE = 'director-fi'
    pass


class FiController(FiServer):
    ROLE = 'control-fi'
    pass


class FiCompute(FiServer):
    ROLE = 'compute-fi'
    pass


class FiCeph(FiServer):
    ROLE = 'ceph-fi'
    pass


class FI(LabNode):
    ROLE = 'ucsm'

    def __init__(self, node_id, lab):
        # https://communities.cisco.com/docs/DOC-51816
        self._vip = 'Not set in FI ctor'
        self._is_sriov = False
        super(FI, self).__init__(node_id=node_id, role=self.ROLE, lab=lab)

    def set_vip(self, vip):
        self._vip = vip

    def get_ucsm_vip(self):
        return self._vip

    def set_sriov(self, sriov):
        self._is_sriov = sriov

    def get_sriov(self):
        return self._is_sriov

    def cmd(self, command):
        from fabric.api import settings, run

        _, username, password = self.get_oob()
        with settings(host_string='{user}@{ip}'.format(user=username, ip=self._vip), password=password, connection_attempts=50, warn_only=False):
            return run(command, shell=False)

    def service_profiles(self):
        return self.cmd(command='scope org; sh service-profile status | no-more | egrep -V "Service|----" | cut -f 1 -d " "')

    def list_allowed_vlans(self, profile, vnic):
        return self.cmd('scope org ; scope service-profile {0}; scope vnic {1}; sh eth-if'.format(profile, vnic) + self._filter(flt='Name:')).split('\n')

    def list_vlans(self):
        return self.cmd('scope eth-uplink; sh vlan' + self._filter(flt='-V "default|VLAN|Name|-----"')).split('\n')

    @staticmethod
    def _filter(flt=None):
        return ' | no-more' + (' | egrep ' + flt if flt else '')

    def list_users(self, flt=None):
        line = self.cmd('scope security ; show local-user' + self._filter(flt=flt or '-V "User Name|-------"'))
        return line.split('\n') if line else []

    def list_user_sessions(self):
        def yield_pairs(l):
            for i in xrange(0, len(l), 2):
                yield l[i:i+2]

        result = self.cmd('scope security ; show user-sessions local detail' + self._filter(flt='"Host:|User:"')).split('\n')
        return [user.split(':')[-1].strip() + '@' + host.split(':')[-1].strip() for user, host in yield_pairs(result)]

    def list_servers(self, flt=None):
        return self.cmd('sh server status' + self._filter(flt=flt or '-V "Server|-------"')).split('\n')

    def list_service_profiles(self, flt=None):
        line = self.cmd(command='scope org; sh service-profile status' + self._filter(flt=flt or '-V "-----|Service Profile Name"'))
        return line.split('\n') if line else []

    def list_mac_pools(self, flt=None):
        line = self.cmd('scope org; sh mac-pool' + self._filter(flt=flt or '-V "Name|----|MAC"'))
        return line.split('\n') if line else []

    def delete_vlans(self, pattern):
        vlan_names = self.cmd('scope eth-uplink; sh vlan|no-more| egrep "{0}" | cut -f 5 -d " "'.format(pattern))
        for vlan_name in vlan_names:
            self.cmd('scope eth-uplink; delete vlan {0}; commit-buffer'.format(vlan_name))

    def create_uuid_pool(self, pool_name, n_uuids):
        return self.cmd('scope org; create uuid-suffix-pool {name}; set assignment-order sequential; create block 1234-000000000001 1234-00000000000{n}; commit-buffer'.format(name=pool_name, n=n_uuids))

    def create_uplink(self, wires):
        for a_b in 'a', 'b':
            created_vpc_ids = set()
            for wire in wires:
                vpc_id = wire.get_pc_id()
                if vpc_id not in created_vpc_ids:
                    self.cmd('scope eth-uplink; scope fabric {a_b}; create port-channel {vpc_id}; commit-buffer'.format(a_b=a_b, vpc_id=vpc_id))
                    created_vpc_ids.add(vpc_id)
                self.cmd('scope eth-uplink; scope fabric {a_b}; scope port-channel {vpc_id}; enter member-port {port_id}; commit-buffer'.format(a_b=a_b, vpc_id=vpc_id, port_id=wire.get_port_s().replace('/', ' ')))

    def create_boot_policies(self, vnics):
        """Creates boot policy for all specified vNICs
        :param vnics: list of vNIC names, e.g. ['pxe', 'eth0']
        """
        for name in vnics:
            self.cmd('scope org; create boot-policy {0}; set boot-mode legacy; commit-buffer'.format(name))
            self.cmd('scope org; scope boot-policy {0}; create lan; set order 1;  create path primary; set vnic {0}; commit-buffer'.format(name))
            self.cmd('scope org; scope boot-policy {0}; create storage; create local; create local-any; set order 2; commit-buffer'.format(name))

    def create_dynamic_vnic_connection_policy(self, policy_name):
        return self.cmd('scope org; create dynamic-vnic-conn-policy {name}; set dynamic-eth 20; set adapter-policy Linux; commit-buffer'.format(name=policy_name))

    def set_dynamic_vnic_connection_policy(self, profile, vnic, policy_name):
        self.cmd('scope org; scope service-profile {p}; scope vnic {v}; set adapter-policy Linux; enter dynamic-conn-policy-ref {n}; commit-buffer'.format(p=profile, v=vnic.get_name(), n=policy_name))

    def list_dynamic_vnic_policy(self, profile):
        return self.cmd('scope org; scope service-profile {0}; sh dynamic-vnic-conn-policy'.format(profile))

    def create_vlans(self, vlans):
        for vlan in vlans:
            self.cmd('scope eth-uplink; create vlan {0} {0}; set sharing none; commit-buffer'.format(vlan))

    def create_server_pool(self, name):
        return self.cmd('scope org; create server-pool {0}; commit-buffer'.format(name))

    def create_ipmi_static(self, server_id, ip, gw, netmask):
        self.cmd('scope server {s_id}; scope cimc; create ext-static-ip; set addr {ip}; set default-gw {gw}; set subnet {netmask}; commit-buffer'.format(s_id=server_id, ip=ip, gw=gw, netmask=netmask))

    def add_server_to_pool(self, server_id, server_pool_name):
        self.cmd('scope org; scope server-pool {0}; create server {1}; commit-buffer'.format(server_pool_name, server_id))

    def create_service_profile(self, name, is_with_sriov):
        self.cmd('scope org; create service-profile {0}; set ipmi-access-profile IPMI; {1} commit-buffer'.format(name, 'set bios-policy SRIOV;' if is_with_sriov else ''))

    def create_vnic_with_vlans(self, profile, vnic, mac, order, vlans):
        self.cmd('scope org; scope service-profile {profile}; create vnic {vnic} fabric a-b; set identity dynamic-mac {mac}; set order {order}; commit-buffer'.format(profile=profile, vnic=vnic, mac=mac, order=order))
        for i, vlan in enumerate(vlans, start=1):
            yes_no = 'yes' if i == 1 else 'no'  # first vlan in the list is a default
            self.cmd('scope org; scope service-profile {profile}; scope vnic {vnic}; create eth-if {vlan}; set default-net {yes_no}; commit-buffer'.format(profile=profile, vnic=vnic, vlan=vlan, yes_no=yes_no))
        self.cmd('scope org; scope service-profile {profile}; scope vnic {vnic}; delete eth-if default; commit-buffer'.format(profile=profile, vnic=vnic))  # remove default VLAN

    def associate_server_with_profile(self, profile, server_id):
        self.cmd('scope org; scope service-profile {profile}; associate server {server_id}; commit-buffer'.format(profile=profile, server_id=server_id))

    def set_boot_policy_to_service_profile(self, profile, policy_name):
        self.cmd('scope org; scope service-profile {profile}; set boot-policy {policy_name}; commit-buffer'.format(profile=profile, policy_name=policy_name))

    def run_kvm_for(self, srv):
        pass
        # self.handle.StartKvmSession(blade=srv, frameTitle=srv.__dict__['Dn'], dumpXml=False)

    def create_user(self, username, password, role='admin'):
        import tempfile
        import platform
        from fabric.api import local

        if self.list_users(flt=username):
            self.delete_users([username])

        if platform.system() == 'Windows':
            raise RuntimeError('expect does not work on Windows!')

        ip, oob_username, oob_password = self.get_oob()
        create_user_script = """#!/usr/bin/expect
set admin_user {admin_user}
set admin_password {admin_password}
set ucsm_ip {ucsm_ip}

set username {username}
set password {password}

spawn ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ${{admin_user}}@${{ucsm_ip}}
expect "Password:" {{send "$admin_password\r"}}

expect "#" {{send "scope security\r"}}
expect "/security #" {{send "create local-user $username\r"}}
expect "/security/local-user* #" {{send "set account-status active\r"}}
expect "/security/local-user* #" {{send "set password\r"}}
expect "Enter a password:" {{send "$password\r"}}
expect "Confirm the password:" {{send "$password\r"}}
expect "/security/local-user* #" {{send "commit-buffer\r"}}
expect "/security/local-user #"
sleep 5
exit
        """.format(admin_user=oob_username, admin_password=oob_password, ucsm_ip=ip, username=username, password=password)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(create_user_script)
        local('expect {0}'.format(f.name))
        self.cmd('scope security; scope local-user {username}; enter role {role}; commit-buffer;'.format(username=username, role=role))

    def delete_users(self, usernames):
        for username in usernames:
            self.cmd('scope security ; delete local-user {0} ; commit-buffer ;'.format(username))

    def configure_for_osp7(self):
        import time

        self.log('Configuring {}'.format(self))

        server_pool_name = 'QA-SERVERS'
        uuid_pool_name = 'QA'
        dynamic_vnic_policy_name = 'dvnic-4'

        self.cleanup()

        n_servers = len(self.lab().get_nodes_by_class(FiServer))  # how many servers UCSM currently sees

        neutron_username, neutron_password = self.lab().get_neutron_creds()
        self.create_user(username=neutron_username, password=neutron_password)  # special user to be used by neutron services
        self.create_uplink(wires=self._upstream_wires)
        self.create_uuid_pool(pool_name=uuid_pool_name, n_uuids=n_servers)
        self.create_boot_policies(vnics=self._lab.get_ucsm_nets_with_pxe())
        self.create_dynamic_vnic_connection_policy(policy_name=dynamic_vnic_policy_name)
        self.create_vlans(vlans=self.lab().get_all_vlans())
        self.create_server_pool(name=server_pool_name)

        # MAC pools
        # for if_name, mac_value, _ in [config['pxe-int-net'], config['user-net'], config['eth0-net'], config['eth1-net']]:
        #    mac_range = '{0}:01 {0}:{1}'.format(mac_value, n_servers)
        #    run('scope org; create mac-pool {0}; set assignment-order sequential; create block {1}; commit-buffer'.format(if_name, mac_range), shell=False)

        # IPMI ip pool
        # ipmi_pool = '{first} {last} {gw} {mask}'.format(first=str(ipmi_net[config['mgmt-net']['start']]),
        # last=str(ipmi_net[config['mgmt-net']['end']]), gw=str(ipmi_net[1]), mask=str(ipmi_net.netmask))
        # run('scope org; scope ip-pool ext-mgmt; set assignment-order sequential; create block {0}; commit-buffer'.format(ipmi_pool), shell=False)

        for wire in self._downstream_wires:
            server = wire.get_peer_node(self)
            server_id, service_profile_name = server.get_ucsm_info()
            is_sriov = self.lab().is_sriov()
            ipmi_ip, _, _ = server.get_ipmi()
            ipmi_net = self.lab().get_ipmi_net()
            ipmi_gw, ipmi_netmask = str(ipmi_net[1]), ipmi_net.netmask
            self.create_ipmi_static(server_id=server_id, ip=ipmi_ip, gw=ipmi_gw, netmask=ipmi_netmask)
            self.add_server_to_pool(server_id, server_pool_name)

            self.create_service_profile(service_profile_name, is_sriov)

            for order, vnic in enumerate(server.get_nics(), start=1):
                vlans = self.lab().get_net_vlans(vnic.get_name())
                self.create_vnic_with_vlans(profile=service_profile_name, vnic=vnic.get_name(), mac=vnic.get_mac(), order=order, vlans=vlans)

                if is_sriov and 'compute' in service_profile_name and vnic.get_name() in ['eth1']:
                    self.set_dynamic_vnic_connection_policy(profile=service_profile_name, vnic=vnic, policy_name=dynamic_vnic_policy_name)

            self.set_boot_policy_to_service_profile(profile=service_profile_name, policy_name='pxe-ext' if 'director' in server.name() else 'pxe-int')

            self.associate_server_with_profile(profile=service_profile_name, server_id=server_id)  # main step - association - here server will be rebooted

        count_attempts = 0
        while count_attempts < 100:
            lines = self.list_service_profiles(flt='Associated')
            if len(lines) == n_servers:
                self.log('finished {0}'.format(self))
                return
            time.sleep(10)
            count_attempts += 1
        raise RuntimeError('failed to associated all service profiles')

    def read_config_ssh(self):
        servers = {}
        ipmi_users = self.cmd('scope org; scope ipmi-access-profile IPMI; sh ipmi-user | egrep -v "Description|---|IPMI" | cut -f 5 -d " "').split('\n')
        if 'cobbler' not in ipmi_users:
            raise Exception('No IPMI user "cobbler" in UCSM! Add it with password "cobbler" manually')

        for profile in self.cmd('scope org; show service-profile | egrep Associated | cut -f 5-35 -d " "').split('\n'):
            if not profile:
                return servers
            split = profile.split()
            profile_name = split[0]
            server_id = split[2]
            ipmi_ip = self.cmd('scope org; scope server {}; scope cimc; sh mgmt-if | egrep [1-9] | cut -f 5 -d " "'.format(server_id))
            if_mac = {}
            for line in self.cmd('scope org; scope service-profile {0}; sh vnic | i {1}:'.format(profile_name, self.lab().id)).split('\n'):
                split = line.split()
                if_mac[split[0]] = split[3]
            server = FiController(lab=self.lab(), node_id=if_mac, role=FiController.ROLE)
            server.set_ucsm_id(server_port=server_id + '/a')
            server.set_oob_creds(ip=ipmi_ip, username='cobbler', password='cobbler')
            servers[profile_name] = server
        return servers

    def delete_service_profiles(self, flt=None):
        for profile in self.list_service_profiles(flt):
            profile_name = profile.split()[0]
            self.cmd('scope org; delete service-profile {0}; commit-buffer'.format(profile_name))

    def delete_mac_pools(self, flt=None):
        for mac_pool in self.list_mac_pools(flt=flt):
            mac_pool_name = mac_pool.split()[0]
            self.cmd('scope org; delete mac-pool {0}; commit-buffer'.format(mac_pool_name))

    def delete_static_cimc_ip(self, flt=None):
        for server in self.list_servers(flt=flt):
            server_id = server.split()[0]
            if self.cmd('scope server {0}; scope cimc; sh ext-static-ip'.format(server_id)):
                self.cmd('scope server {0}; scope cimc; delete ext-static-ip; commit-buffer'.format(server_id))

    def cleanup(self):
        self.delete_service_profiles()
        self.delete_mac_pools()
        for server_pool in self.cmd('scope org; sh server-pool | no-more | egrep -V "Name|----|MAC" | cut -f 5 -d " "').split():
            self.cmd('scope org; delete server-pool {0}; commit-buffer'.format(server_pool))
        for uuid_pool in self.cmd('scope org; sh uuid-suffix-pool | no-more | egrep -V "Name|----|UUID" | cut -f 5 -d " "').split():
            self.cmd('scope org; delete uuid-suffix-pool {0}; commit-buffer'.format(uuid_pool))
        for boot_policy in self.cmd('scope org; sh boot-policy | no-more | egrep -V "Name|----|UUID" | cut -f 5 -d " "').split():
            self.cmd('scope org; delete boot-policy {0}; commit-buffer'.format(boot_policy))
        for dyn_vnic_policy in self.cmd('scope org; show dynamic-vnic-conn-policy detail | no-more | egrep "Name:" | cut -f 6 -d " "').split():
            self.cmd('scope org; delete dynamic-vnic-conn-policy {0}; commit-buffer'.format(dyn_vnic_policy))
        for vlan in self.cmd('scope eth-uplink; sh vlan | no-more | eg -V "default|VLAN|Name|-----" | cut -f 5 -d " "').split():
            self.cmd('scope eth-uplink; delete vlan {0}; commit-buffer'.format(vlan))
        self.delete_static_cimc_ip('Complete')
#            run('acknowledge server {0}  ;  commit-buffer'.format(server_num), shell=False)
        for block in self.cmd('scope org; scope ip-pool ext-mgmt; sh block | egrep [1-9] | cut -f 5-10 -d " "').split('\n'):
            if block:
                self.cmd('scope org; scope ip-pool ext-mgmt; delete block {0}; commit-buffer'.format(block))
        for pp in self.cmd('scope system; scope vm-mgmt; scope profile-set; show port-profile detail | no-more | egrep "Name:" | cut -f 6 -d " "').split('\n'):
            if pp.strip():
                self.cmd("end; scope system; scope vm-mgmt; scope profile-set; delete port-profile {0} ; commit-buffer".format(pp.strip()))
        for fabric in 'a', 'b':
            for port_channel_id in self.cmd('scope eth-uplink; scope fabric {0}; show port-channel detail | egrep "Port Channel Id:" | cut -f 8 -d " "'.format(fabric)).split():
                if port_channel_id.strip():
                    self.cmd('scope eth-uplink; scope fabric {0}; delete port-channel {1}; commit-buffer'.format(fabric, port_channel_id.strip()))
        self.log('finished')


# @task
# def read_config_sdk(host='10.23.228.253', username='admin', password='cisco'):
#     """Reads config needed for OSP7"""
#     import UcsSdk
#
#     configuration = {'nodes': []}
#     u = UcsSdk.UcsHandle()
#     try:
#         u.Login(name=host, username=username, password=password)
#
#         mo_list = u.GetManagedObject(inMo=None, classId=UcsSdk.LsServer.ClassId(), params=None)
#         for mo_server in mo_list:
#             if mo_server.Name.startswith('QA'):
#                 mo_eth0 = u.GetManagedObject(inMo=None, classId=None, params={UcsSdk.OrgOrg.DN: "org-root/ls-{}/ether-eth0".format(mo_server.Name)})
#                 mac = mo_eth0[0].Addr
#                 n_cpu = 4
#                 memory_gb = 128
#                 disk_size_gb = 2000
#                 arch = 'x86_64'
#                 ipmi_user = username
#                 ipmi_password = password
#                 ipmi_ip = 'xxxxx'
#                 configuration['nodes'].append(__ucs_descriptor(mac=mac, n_cpu=n_cpu, memory_gb=memory_gb, disk_size_gb=disk_size_gb, arch=arch,
#                                                                ipmi_user=ipmi_user, ipmi_password=ipmi_password, ipmi_ip=ipmi_ip))
#         print configuration
#         return configuration
#     except Exception as ex:
#         print ex
#     finally:
#         u.Logout()
#
#
# class UcsmServer(object):
#     def __init__(self, server_num, profile_name, ipmi_ip, ipmi_username, ipmi_password, pxe_mac):
#         self.server_num = server_num
#         self.profile_name = profile_name
#         self.ipmi_ip = ipmi_ip
#         self.ipmi_username = ipmi_username
#         self.ipmi_password = ipmi_password
#         self.pxe_mac = pxe_mac
#
#         self.arch = 'x86_64'
#         self.n_cores = 20
#         self.mem_size_gb = 128
#         self.disk_size_gb = 500
#
#     def __repr__(self):
#         return 'N{num}: profile: {profile} ipmi: {user}:{password}@{ip} PXE: {mac} '.format(num=self.server_num,
#                                                                                             profile=self.profile_name,
#                                                                                             user=self.ipmi_username,
#                                                                                             password=self.ipmi_password,
#                                                                                             ip=self.ipmi_ip,
#                                                                                             mac=self.pxe_mac)
#
#     @staticmethod
#     def json(servers):
#         from StringIO import StringIO
#         import json
#
#         config = {'nodes': []}
#         for server in servers:
#             config['nodes'].append({'mac': server.pxe_mac,
#                                     'cpu': server.n_cores,
#                                     'memory': server.mem_size_gb,
#                                     'disk': server.disk_size_gb,
#                                     'arch': server.arch,
#                                     'pm_type': "pxe_ipmitool",
#                                     'pm_user': server.ipmi_username,
#                                     'pm_password': server.ipmi_password,
#                                     'pm_addr': server.ipmi_ip})
#         return StringIO(json.dumps(config))
# @task
# def ucsm(host='10.23.228.253', username='admin', password='cisco', service_profile_name='test_profile'):
#     import UcsSdk
#
#     try:
#         u = UcsSdk.UcsHandle()
#         u.Login(name=host, username=username, password=password)
#         org = u.GetManagedObject(inMo=None, classId=UcsSdk.OrgOrg.ClassId(), params={UcsSdk.OrgOrg.LEVEL: '0'})
#         u.AddManagedObject(inMo=org, classId=UcsSdk.LsServer.ClassId(), params={UcsSdk.LsServer.NAME: service_profile_name}, modifyPresent=True)
#     except Exception as ex:
#         print ex
#     finally:
#         u.Logout()
#
#
# @task
# def sandhya(host='10.23.228.253', username='admin', password='cisco'):
#     import UcsSdk
#
#     class Const(object):
#         VNIC_PATH_PREFIX = "/vnic-"
#         VLAN_PATH_PREFIX = "/if-"
#         VLAN_PROFILE_PATH_PREFIX = "/net-"
#         VLAN_PROFILE_NAME_PREFIX = "OS-"
#         PORT_PROFILE_NAME_PREFIX = "OS-PP-"
#         CLIENT_PROFILE_NAME_PREFIX = "OS-CL-"
#         CLIENT_PROFILE_PATH_PREFIX = "/cl-"
#
#         SERVICE_PROFILE_PATH_PREFIX = "org-root/ls-"
#         ETH0 = "/ether-eth0"
#         ETH1 = "/ether-eth1"
#
#     const = Const()
#
#     def make_vlan_name(vlan_id):
#         return const.VLAN_PROFILE_NAME_PREFIX + str(vlan_id)
#
#     vlan_id = 333
#     service_profile = 'QA14'
#
#     handle = UcsSdk.UcsHandle()
#     handle.Login(name=host, username=username, password=password)
#
#     service_profile_path = (const.SERVICE_PROFILE_PATH_PREFIX + str(service_profile))
#     vlan_name = make_vlan_name(vlan_id)
#
#     obj = handle.GetManagedObject(inMo=None, classId=UcsSdk.LsServer.ClassId(), params={UcsSdk.LsServer.DN: service_profile_path})
#     for eth in handle.GetManagedObject(inMo=obj, classId=UcsSdk.VnicEther.ClassId(), params={}):
#         vlan_path = (const.VLAN_PATH_PREFIX + vlan_name)
#         eth_if = handle.AddManagedObject(inMo=eth, classId=UcsSdk.VnicEtherIf.ClassId(), modifyPresent=True, params={UcsSdk.VnicEtherIf.DN: vlan_path,
#                                                                                                                      UcsSdk.VnicEtherIf.NAME: vlan_name,
#                                                                                                                      UcsSdk.VnicEtherIf.DEFAULT_NET: "no"}, )
#
#     handle.CompleteTransaction()
#
#
# @task
# def ucsm_backup(host='172.29.172.177', username='admin', password='cisco'):
#     """Take config backup"""
#     import UcsSdk
#
#     try:
#         u = UcsSdk.UcsHandle()
#         u.Login(name=host, username=username, password=password)
#         u.BackupUcs(type='config-all', pathPattern='./ucsm-config-all.xml')  # also possible config-system, config-logical, full-state
#     finally:
#         u.Logout()
#
#
# @task
# def restore_backup(host='172.29.172.177', username='admin', password='cisco', backup_path='lab/configs/ucsm/g10-ucsm-config.xml'):
#     """Upload given xml to restore given UCSM to the state when backup was taken"""
#     import UcsSdk
#
#     try:
#         u = UcsSdk.UcsHandle()
#         u.Login(name=host, username=username, password=password)
#         u.ImportUcsBackup(path=backup_path, merge=False, dumpXml=False)
#     finally:
#         u.Logout()
