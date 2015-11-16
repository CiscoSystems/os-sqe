from fabric.api import task


@task
def read_config_ssh(yaml_path, is_director=True):
    """Reads config needed for OSP7 via ssh to UCSM"""
    from lab.Server import Server
    from fabric.api import settings, run
    from lab.WithConfig import read_config_from_file

    config = read_config_from_file(yaml_path=yaml_path)

    ucsm_ip = config['ucsm']['host']
    ucsm_username = config['ucsm']['username']
    ucsm_password = config['ucsm']['password']

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
            if not is_director and server_id == str(config['ucsm']['director-server-id']):
                continue
            ipmi_ip = run('scope org; scope server {}; scope cimc; sh mgmt-if | egrep [1-9] | cut -f 5 -d " "'.format(server_id), shell=False, quiet=True)
            if_mac = {}
            for line in run('scope org; scope service-profile {0}; sh vnic | i {1}:'.format(profile_name, config['lab-id']), shell=False, quiet=True).split('\n'):
                split = line.split()
                if_mac[split[0]] = split[3]
            server = Server(ip='NotKnownByUCSM', username='NotKnownByUCSM', password='NotKnownByUCSM')
            server.set_ipmi(ip=ipmi_ip, username='cobbler', password='cobbler')
            server.set_ucsm(ip=ucsm_ip, username=ucsm_username, password=ucsm_password, service_profile=profile_name, server_id=server_id, iface_mac=if_mac)
            if server_id == str(config['ucsm']['director-server-id']):
                profile_name = server_id
            servers[profile_name] = server
    return servers


@task
def cleanup(host, username, password):
    from fabric.api import settings, run

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
        for block in run('scope org; scope ip-pool ext-mgmt; sh block | egrep [1-9] | cut -f 5-10 -d " "', shell=False).split('\n'):
            if block:
                run('scope org; scope ip-pool ext-mgmt; delete block {0}; commit-buffer'.format(block), shell=False)
        for pp in run('scope system; scope vm-mgmt; scope profile-set; show port-profile detail | no-more | egrep "Name:" | cut -f 6 -d " "', shell=False).split('\n'):
            if pp.strip():
                run("end; scope system; scope vm-mgmt; scope profile-set; delete port-profile {0} ; commit-buffer".format(pp.strip()), shell=False)
        for fabric in 'a', 'b':
            for port_channel_id in run('scope eth-uplink; scope fabric {0}; show port-channel detail | egrep "Port Channel Id:" | cut -f 8 -d " "'.format(fabric), shell=False).split():
                if port_channel_id.strip():
                    run('scope eth-uplink; scope fabric {0}; delete port-channel {1}; commit-buffer'.format(fabric, port_channel_id.strip()), shell=False)


@task
def configure_for_osp7(yaml_path):
    from fabric.api import settings, run
    import os
    import yaml
    from netaddr import IPNetwork

    if not os.path.isfile(yaml_path):
        raise IOError('{0} not found. Provide full path to your yaml config file'.format(yaml_path))

    with open(yaml_path) as f:
        config = yaml.load(f)

    ipmi_net = IPNetwork(config['mgmt-net']['cidr'])
    host = config['ucsm']['host']
    username = config['ucsm']['username']
    password = config['ucsm']['password']

    server_pool_name = 'QA-SERVERS'
    uuid_pool_name = 'QA'
    dynamic_vnic_policy_name = 'dvnic-4'

    with settings(host_string='{user}@{ip}'.format(user=username, ip=host), password=password, connection_attempts=50, warn_only=False):
        server_nums = run('sh server status | egrep "Complete$" | cut -f 1 -d " "', shell=False).split()
        n_servers = len(server_nums)  # how many servers UCSM currently sees
        if config['mgmt-net']['end'] - config['mgmt-net']['start'] + 1 < n_servers:
            raise Exception("mgmt-net less than servers amount. {0}".format(config['mgmt-net']))

        # Create up-links (port-channels)
        for fabric in 'a', 'b':
            run('scope eth-uplink; scope fabric {0}; create port-channel {1}; commit-buffer'.format(fabric, config['ucsm']['uplink-vpc-id']), shell=False)
            for port in config['ucsm']['uplink-ports']:
                slot_id, port_id = port.split('/')
                run('scope eth-uplink; scope fabric {0}; scope port-channel {1}; enter member-port {2} {3}; commit-buffer'.format(fabric, config['ucsm']['uplink-vpc-id'], slot_id, port_id), shell=False)

        # UUID pool
        run('scope org; create uuid-suffix-pool {name}; set assignment-order sequential; create block 1234-000000000001 1234-00000000000{n}; commit-buffer'.format(
            name=uuid_pool_name, n=n_servers), shell=False)

        # Boot policy
        for card in [config['pxe-ext-net']['iface-name'], config['pxe-int-net']['iface-name']]:
            run('scope org; create boot-policy {0}; set boot-mode legacy; commit-buffer'.format(card), shell=False)
            run('scope org; scope boot-policy {0}; create lan; set order 1;  create path primary; set vnic {0}; commit-buffer'.format(card), shell=False)
            run('scope org; scope boot-policy {0}; create storage; create local; create local-any; set order 2; commit-buffer'.format(card), shell=False)

        # Dynamic vnic connection policy
        if config['is-add-sriov']:
            run('scope org; create dynamic-vnic-conn-policy {name}; set dynamic-eth 4; set adapter-policy Linux; commit-buffer'.format(name=dynamic_vnic_policy_name), shell=False)

        # MAC pools
        # for if_name, mac_value, _ in [config['pxe-int-net'], config['user-net'], config['eth0-net'], config['eth1-net']]:
        #    mac_range = '{0}:01 {0}:{1}'.format(mac_value, n_servers)
        #    run('scope org; create mac-pool {0}; set assignment-order sequential; create block {1}; commit-buffer'.format(if_name, mac_range), shell=False)

        # VLANs
        for net_name in ['user-net', 'pxe-int-net', 'eth0-net', 'eth1-net']:
            net = config[net_name]
            run('scope eth-uplink; create vlan {0} {1}; set sharing none; commit-buffer'.format(net['iface-name'], net['vlan']), shell=False)

        # IPMI ip pool
        # ipmi_pool = '{first} {last} {gw} {mask}'.format(first=str(ipmi_net[config['mgmt-net']['start']]), last=str(ipmi_net[config['mgmt-net']['end']]), gw=str(ipmi_net[1]), mask=str(ipmi_net.netmask))
        # run('scope org; scope ip-pool ext-mgmt; set assignment-order sequential; create block {0}; commit-buffer'.format(ipmi_pool), shell=False)

        # Server pool
        run('scope org; create server-pool {0}; commit-buffer'.format(server_pool_name), shell=False)

        for i, server_id in enumerate(server_nums):
            if '/' in server_id:
                b_c_id = 'B{0}:{1:02}'.format(int(server_id.split('/')[0]), int(server_id.split('/')[1]))
            else:
                b_c_id = 'C0:{0:02}'.format(int(server_id))

            profile = 'G{0}-{1}'.format(config['lab-id'], b_c_id)

            if server_id == str(config['ucsm']['director-server-id']):
                profile += '-' + config['ucsm']['director-profile']
            # add IPMI static ip:
            addr = ipmi_net[config['mgmt-net']['start'] + i]
            gw = ipmi_net[1]
            net_mask = str(ipmi_net.netmask)
            run('scope server {0}; scope cimc; create ext-static-ip; set addr {1}; set default-gw {2}; set subnet {3}; commit-buffer'.format(server_id, addr, gw, net_mask), shell=False)

            # add server to server pool
            run('scope org; scope server-pool {0}; create server {1}; commit-buffer'.format(server_pool_name, server_id), shell=False)

            # create service profile
            run('scope org; create service-profile {0}; set ipmi-access-profile IPMI;  commit-buffer'.format(profile, 'set bios-policy SRIOV;' if config['is-add-sriov'] else ''), shell=False)

            for order, net_name in enumerate(['eth0-net', 'eth1-net', 'pxe-int-net', 'user-net'], start=1):
                vnic = config[net_name]['iface-name']
                mac = config[net_name]['mac-tmpl'].format(lab_id=config['lab-id'], b_c_id=b_c_id)
                # add VNIC
                run('scope org; scope service-profile {0}; create vnic {1} fabric a-b; set identity dynamic-mac {2}; set order {3}; commit-buffer'.format(profile, vnic, mac, order), shell=False)
                # add VLAN to vNIC
                run('scope org; scope service-profile {0}; scope vnic {1}; create eth-if {1}; set default-net yes; commit-buffer'.format(profile, vnic), shell=False)
                # remove default VLAN
                run('scope org; scope service-profile {0}; scope vnic {1}; delete eth-if default; commit-buffer'.format(profile, vnic), shell=False)

            if server_id == str(config['ucsm']['director-server-id']):
                # special vNIC to have this server booted via external PXE
                vnic = config['pxe-ext-net']['iface-name']
                mac = config['pxe-ext-net']['mac-tmpl'].format(lab_id=config['lab-id'], b_c_id=b_c_id)
                run('scope org; scope service-profile {0}; create vnic {1} fabric a-b; set identity dynamic-mac {2}; commit-buffer'.format(profile, vnic, mac), shell=False)
                run('scope org; scope service-profile {0}; set boot-policy {1}; commit-buffer'.format(profile, config['pxe-ext-net']['iface-name']), shell=False)
            else:
                run('scope org; scope service-profile {0}; set boot-policy {1}; commit-buffer'.format(profile, config['pxe-int-net']['iface-name']), shell=False)
                # set dynamic vnic connection policy
                if config['is-add-sriov'] and config['ucsm']['director-server-id'] != server_id and vnic in ['eth1']:
                    run('scope org; scope service-profile {0}; scope vnic {1}; set adapter-policy Linux; enter dynamic-conn-policy-ref {2}; commit-buffer'.format(profile, vnic, dynamic_vnic_policy_name), shell=False)

            # main step - association - here server will be rebooted
            run('scope org; scope service-profile {0}; associate server {1}; commit-buffer'.format(profile, server_id), shell=False)


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
