from fabric.api import task


class Ucsm(object):
    def __init__(self, ucsm_ip, ucsm_username, ucsm_password):
        self.ucsm_ip = ucsm_ip
        self.ucsm_username = ucsm_username
        self.ucsm_password = ucsm_password

    def cmd(self, command):
        from fabric.api import settings, run
    
        with settings(host_string='{user}@{ip}'.format(user=self.ucsm_username, ip=self.ucsm_ip), password=self.ucsm_password, connection_attempts=50, warn_only=False):
            return run(command, shell=False).split()

    def service_profiles(self):
        return self.cmd(command='scope org; sh service-profile status | no-more | egrep -V "Service|----" | cut -f 1 -d " "')

    def allowed_vlans(self, profile, vnic):
        return self.cmd('scope org ; scope service-profile {0}; scope vnic {1}; sh eth-if | no-more | egrep "Name:" | cut -f 6 -d " "'.format(profile, vnic))

    def vlans(self):
        return self.cmd('scope eth-uplink; sh vlan | no-more | eg -V "default|VLAN|Name|-----" | cut -f 5 -d " "')

    def user_sessions(self):
        return self.cmd('scope security ; show user-sessions local detail | no-more | egrep "Pid:" | cut -f 6 -d " "')


@task
def read_config_ssh(yaml_path, is_director=True):
    """Reads config needed for OSP7 via ssh to UCSM
    :param yaml_path:
    :param is_director:
    :return:
    """
    from lab.server import Server
    from fabric.api import settings, run
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=yaml_path)

    ucsm_ip, ucsm_username, ucsm_password = l.ucsm_creds()

    servers = {}
    with settings(host_string='{user}@{ip}'.format(user=ucsm_username, ip=ucsm_ip), password=ucsm_password, connection_attempts=50, warn_only=False):
        ipmi_users = run('scope org; scope ipmi-access-profile IPMI; sh ipmi-user | egrep -v "Description|---|IPMI" | cut -f 5 -d " "', shell=False, quiet=True).split('\n')
        if 'cobbler' not in ipmi_users:
            raise Exception('No IPMI user "cobbler" in UCSM! Add it with password "cobbler" manually')

        for profile in run('scope org; show service-profile | egrep Associated | cut -f 5-35 -d " "', shell=False, quiet=True).split('\n'):
            if not profile:
                return servers
            split = profile.split()
            profile_name = split[0]
            server_id = split[2]
            if not is_director and 'director' in profile_name:
                continue
            ipmi_ip = run('scope org; scope server {}; scope cimc; sh mgmt-if | egrep [1-9] | cut -f 5 -d " "'.format(server_id), shell=False, quiet=True)
            if_mac = {}
            for line in run('scope org; scope service-profile {0}; sh vnic | i {1}:'.format(profile_name, l.id), shell=False, quiet=True).split('\n'):
                split = line.split()
                if_mac[split[0]] = split[3]
            dynamic_policy_line = run('scope org; scope service-profile {0}; sh dynamic-vnic-conn-policy'.format(profile_name), shell=False, quiet=True)
            server = Server(ip='NotKnownByUCSM', username='NotKnownByUCSM', password='NotKnownByUCSM')
            server.set_ipmi(ip=ipmi_ip, username='cobbler', password='cobbler')
            server.set_ucsm(ip=ucsm_ip, username=ucsm_username, password=ucsm_password, service_profile=profile_name, server_id=server_id, is_sriov=len(dynamic_policy_line) != 0)
            server.role = profile_name.split('-')[-1]
            if 'director' in profile_name:
                profile_name = 'director'
            servers[profile_name] = server
    return servers


@task
def cleanup(host, username, password):
    from fabric.api import settings, run
    from lab.logger import lab_logger

    with settings(host_string='{user}@{ip}'.format(user=username, ip=host), password=password, connection_attempts=50, warn_only=False):
        for profile in run('scope org; sh service-profile status | no-more | egrep -V "Service|----" | cut -f 1 -d " "', shell=False).split():
            run('scope org; delete service-profile {0}; commit-buffer'.format(profile), shell=False)
        for mac_pool in run('scope org; sh mac-pool | no-more | egrep -V "Name|----|MAC" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete mac-pool {0}; commit-buffer'.format(mac_pool), shell=False)
        for server_pool in run('scope org; sh server-pool | no-more | egrep -V "Name|----|MAC" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete server-pool {0}; commit-buffer'.format(server_pool), shell=False)
        for uuid_pool in run('scope org; sh uuid-suffix-pool | no-more | egrep -V "Name|----|UUID" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete uuid-suffix-pool {0}; commit-buffer'.format(uuid_pool), shell=False)
        for boot_policy in run('scope org; sh boot-policy | no-more | egrep -V "Name|----|UUID" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete boot-policy {0}; commit-buffer'.format(boot_policy), shell=False)
        for dyn_vnic_policy in run('scope org; show dynamic-vnic-conn-policy detail | no-more | egrep "Name:" | cut -f 6 -d " "', shell=False).split():
            run('scope org; delete dynamic-vnic-conn-policy {0}; commit-buffer'.format(dyn_vnic_policy), shell=False)
        for vlan in run('scope eth-uplink; sh vlan | no-more | eg -V "default|VLAN|Name|-----" | cut -f 5 -d " "', shell=False).split():
            run('scope eth-uplink; delete vlan {0}; commit-buffer'.format(vlan), shell=False)
        for server_num in run('sh server status | no-more | egrep "Complete$" | cut -f 1 -d " "', shell=False).split():
            if run('scope server {0}; scope cimc; sh ext-static-ip'.format(server_num), shell=False):
                run('scope server {0}; scope cimc; delete ext-static-ip; commit-buffer'.format(server_num), shell=False)
#            run('acknowledge server {0}  ;  commit-buffer'.format(server_num), shell=False)
        for block in run('scope org; scope ip-pool ext-mgmt; sh block | egrep [1-9] | cut -f 5-10 -d " "', shell=False).split('\n'):
            if block:
                run('scope org; scope ip-pool ext-mgmt; delete block {0}; commit-buffer'.format(block), shell=False)
        for pp in run('scope system; scope vm-mgmt; scope profile-set; show port-profile detail | no-more | egrep "Name:" | cut -f 6 -d " "', shell=False).split('\n'):
            if pp.strip():
                run("end; scope system; scope vm-mgmt; scope profile-set; delete port-profile {0} ; commit-buffer".format(pp.strip()), shell=False)
        for fabric in 'a', 'b':
            for port_channel_id in run('scope eth-uplink; scope fabric {0}; show port-channel detail | egrep "Port Channel Id:" | cut -f 8 -d " "'.format(fabric),
                                       shell=False).split():
                if port_channel_id.strip():
                    run('scope eth-uplink; scope fabric {0}; delete port-channel {1}; commit-buffer'.format(fabric, port_channel_id.strip()), shell=False)
    lab_logger.info('finished')


def configure_for_osp7(yaml_path):
    from fabric.api import settings, run
    import time
    from lab.laboratory import Laboratory
    from lab.logger import lab_logger

    lab_logger.info('Configuring UCSM ' + yaml_path)
    lab = Laboratory(config_path=yaml_path)

    server_pool_name = 'QA-SERVERS'
    uuid_pool_name = 'QA'
    dynamic_vnic_policy_name = 'dvnic-4'

    ucsm_host, ucsm_user, ucsm_password = lab.ucsm_creds()

    cleanup(host=ucsm_host, username=ucsm_user, password=ucsm_password)

    with settings(host_string='{user}@{ip}'.format(user=ucsm_user, ip=ucsm_host), password=ucsm_password, connection_attempts=50, warn_only=False):
        server_ids = run('sh server status | egrep "Complete$" | cut -f 1 -d " "', shell=False).split()
        n_servers = len(server_ids)  # how many servers UCSM currently sees

        # Create up-links (port-channels)
        for fabric in 'a', 'b':
            run('scope eth-uplink; scope fabric {0}; create port-channel {1}; commit-buffer'.format(fabric, lab.ucsm_uplink_vpc_id()), shell=False)
            for port_id in lab.ucsm_uplink_ports():
                run('scope eth-uplink; scope fabric {fabric}; scope port-channel {vpc_id}; enter member-port {port_id}; commit-buffer'.format(
                        fabric=fabric,
                        vpc_id=lab.ucsm_uplink_vpc_id(),
                        port_id=port_id), shell=False)

        # UUID pool
        run('scope org; create uuid-suffix-pool {name}; set assignment-order sequential; create block 1234-000000000001 1234-00000000000{n}; commit-buffer'.format(
            name=uuid_pool_name, n=n_servers), shell=False)

        # Boot policy
        for if_name in lab.ucsm_nets_with_pxe():
            run('scope org; create boot-policy {0}; set boot-mode legacy; commit-buffer'.format(if_name), shell=False)
            run('scope org; scope boot-policy {0}; create lan; set order 1;  create path primary; set vnic {0}; commit-buffer'.format(if_name), shell=False)
            run('scope org; scope boot-policy {0}; create storage; create local; create local-any; set order 2; commit-buffer'.format(if_name), shell=False)

        # Dynamic vnic connection policy
        if lab.ucsm_is_any_sriov():
            run('scope org; create dynamic-vnic-conn-policy {name}; set dynamic-eth 4; set adapter-policy Linux; commit-buffer'.format(name=dynamic_vnic_policy_name), shell=False)

        # MAC pools
        # for if_name, mac_value, _ in [config['pxe-int-net'], config['user-net'], config['eth0-net'], config['eth1-net']]:
        #    mac_range = '{0}:01 {0}:{1}'.format(mac_value, n_servers)
        #    run('scope org; create mac-pool {0}; set assignment-order sequential; create block {1}; commit-buffer'.format(if_name, mac_range), shell=False)

        # VLANs
        for vlan in lab.ucsm_vlans():
            run('scope eth-uplink; create vlan {0} {0}; set sharing none; commit-buffer'.format(vlan), shell=False)

        # IPMI ip pool
        # ipmi_pool = '{first} {last} {gw} {mask}'.format(first=str(ipmi_net[config['mgmt-net']['start']]),
        # last=str(ipmi_net[config['mgmt-net']['end']]), gw=str(ipmi_net[1]), mask=str(ipmi_net.netmask))
        # run('scope org; scope ip-pool ext-mgmt; set assignment-order sequential; create block {0}; commit-buffer'.format(ipmi_pool), shell=False)

        # Server pool
        run('scope org; create server-pool {0}; commit-buffer'.format(server_pool_name), shell=False)

        for server in lab.servers:
            server_id = server.ucsm_server_id()

            # add IPMI static ip:
            ipmi_ip, _, _ = server.ipmi_creds()
            run('scope server {server_id}; scope cimc; create ext-static-ip; set addr {ipmi_ip}; set default-gw {ipmi_gw}; set subnet {ipmi_net_mask}; commit-buffer'.format(
                    server_id=server_id,
                    ipmi_ip=ipmi_ip,
                    ipmi_gw=lab.ipmi_gw,
                    ipmi_net_mask=lab.ipmi_netmask), shell=False)

            # add server to server pool
            run('scope org; scope server-pool {0}; create server {1}; commit-buffer'.format(server_pool_name, server_id), shell=False)

            # create service profile
            run('scope org; create service-profile {profile}; set ipmi-access-profile IPMI; {sriov_policy} commit-buffer'.format(
                    profile=server.ucsm_profile(),
                    sriov_policy='set bios-policy SRIOV;' if server.ucsm_is_sriov() else ''), shell=False)

            for nic_name, nic_mac, nic_order, nic_vlans in server.nics:
                # create vNIC
                run('scope org; scope service-profile {profile}; create vnic {nic_name} fabric a-b; set identity dynamic-mac {nic_mac}; set order {order}; commit-buffer'.format(
                        profile=server.ucsm_profile(),
                        nic_name=nic_name,
                        nic_mac=nic_mac,
                        order=nic_order), shell=False)
                # add default VLAN to vNIC
                run('scope org; scope service-profile {profile}; scope vnic {nic_name}; create eth-if {vlan}; set default-net yes; commit-buffer'.format(
                        profile=server.ucsm_profile(),
                        nic_name=nic_name,
                        vlan=nic_vlans[0]), shell=False)
                for vlan in nic_vlans[1:]:
                    run('scope org; scope service-profile {profile}; scope vnic {nic_name}; create eth-if {vlan}; set default-net no; commit-buffer'.format(
                            profile=server.ucsm_profile(),
                            nic_name=nic_name,
                            vlan=vlan), shell=False)
                # remove default VLAN
                run('scope org; scope service-profile {profile}; scope vnic {nic_name}; delete eth-if default; commit-buffer'.format(
                        profile=server.ucsm_profile(),
                        nic_name=nic_name), shell=False)
                # set dynamic vnic connection policy
                if server.ucsm_is_sriov() and nic_name in ['eth1']:
                    run('scope org; scope service-profile {profile}; scope vnic {nic_name}; set adapter-policy Linux; enter dynamic-conn-policy-ref {pn}; commit-buffer'.format(
                            profile=server.ucsm_profile(),
                            nic_name=nic_name,
                            pn=dynamic_vnic_policy_name), shell=False)

            # boot-policy
            run('scope org; scope service-profile {profile}; set boot-policy {boot_policy_name}; commit-buffer'.format(
                    profile=server.ucsm_profile(),
                    boot_policy_name='pxe-ext' if 'director' in server.role else 'pxe-int'), shell=False)

            # main step - association - here server will be rebooted
            run('scope org; scope service-profile {profile}; associate server {server_id}; commit-buffer'.format(
                    profile=server.ucsm_profile(),
                    server_id=server.ucsm_server_id()), shell=False)

        count_attempts = 0

        while count_attempts < 100:
            lines = run('scope org; show service-profile | egrep Associated', shell=False).split('\n')
            if len(lines) == len(lab.servers):
                lab_logger.info('finished UCSM ' + yaml_path)
                return
            time.sleep(10)
            count_attempts += 1
        raise RuntimeError('failed to associated all service profiles')


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
