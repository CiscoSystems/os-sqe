from fabric.api import task


def __ucs_descriptor(mac, n_cpu, memory_gb, disk_size_gb, arch, ipmi_user, ipmi_password, ipmi_ip):
    return {'mac': [mac], 'cpu': n_cpu, 'memory': memory_gb, 'disk': disk_size_gb, 'arch': arch,
            'pm_type': "pxe_ipmitool", 'pm_user': ipmi_user, 'pm_password': ipmi_password, "pm_addr": ipmi_ip}


@task
def read_config_sdk(host='10.23.228.253', username='admin', password='cisco'):
    """Reads config needed for OSP7"""
    import UcsSdk

    configuration = {'nodes': []}
    try:
        u = UcsSdk.UcsHandle()
        u.Login(name=host, username=username, password=password)

        mo_list = u.GetManagedObject(inMo=None, classId=UcsSdk.LsServer.ClassId(), params=None)
        for mo_server in mo_list:
            if mo_server.Name.startswith('QA'):
                mo_eth0 = u.GetManagedObject(inMo=None, classId=None, params={UcsSdk.OrgOrg.DN: "org-root/ls-{}/ether-eth0".format(mo_server.Name)})
                mac = mo_eth0[0].Addr
                n_cpu = 4
                memory_gb = 128
                disk_size_gb = 2000
                arch = 'x86_64'
                ipmi_user = username
                ipmi_password = password
                ipmi_ip = 'xxxxx'
                configuration['nodes'].append(__ucs_descriptor(mac=mac, n_cpu=n_cpu, memory_gb=memory_gb, disk_size_gb=disk_size_gb, arch=arch,
                                                               ipmi_user=ipmi_user, ipmi_password=ipmi_password, ipmi_ip=ipmi_ip))
        print configuration
        return configuration
    except Exception as ex:
        print ex
    finally:
        u.Logout()


class UcsmServer(object):
    def __init__(self, server_num, profile_name):
        self.server_num = server_num
        self.profile_name = profile_name
        self.ipmi = {'ip': None, 'username': None, 'password': 'cisco'}
        self.nics = {}
        self.arch = 'x86_64'
        self.n_cores = 20
        self.mem_size_gb = 128
        self.disk_size_gb = 500

    def __repr__(self):
        return 'N{num}: profile: {profile} ipmi: {user}:{password}@{ip} PXE: {mac} '.format(num=self.server_num,
                                                                                            profile=self.profile_name,
                                                                                            user=self.ipmi['username'],
                                                                                            password=self.ipmi['password'],
                                                                                            ip=self.ipmi['ip'],
                                                                                            mac=self.nics['eth0'])

    def add_nic(self, name, mac):
        self.nics[name] = mac

    def set_hardware(self, mem_size_mb, n_cores):
        self.mem_size_gb = int(mem_size_mb)/1024
        self.n_cores = n_cores
        self.disk_size_gb = 500

    def set_ipmi(self, ip, username):
        self.ipmi['ip'] = ip
        self.ipmi['username'] = username


@task
def read_config_ssh(host='10.23.228.253', username='admin', password='cisco'):
    """Reads config needed for OSP7 via ssh to UCSM"""
    from fabric.api import settings, run
    import re

    mac_re = re.compile(r'([0-9A-F]{2}[:-]){5}([0-9A-F]{2})', re.I)

    def normalize_output(multiline):
        multiline = multiline.split('\r\n')
        return multiline if len(multiline) > 1 else multiline[0]

    servers = {}
    with settings(host_string='{user}@{ip}'.format(user=username, ip=host), password=password, connection_attempts=50, warn_only=False):
        ipmi_username, _, _ = normalize_output(run('scope org; scope ipmi-access-profile IPMI; sh ipmi-user | egrep -v "User|---|IPMI"', shell=False, quiet=True)).split()

        for profile in normalize_output(run('scope org; show service-profile | egrep Associated', shell=False, quiet=True)):
            profile_name, _, server_num, _, _ = profile.split()
            ipmi_ip, _, _, _ = normalize_output(run('scope org; scope server {}; scope cimc; sh mgmt-if | egrep [1-9]'.format(server_num), shell=False, quiet=True)).split()
            server = UcsmServer(server_num=server_num, profile_name=profile_name)
            server.set_ipmi(ip=ipmi_ip, username=ipmi_username)
            for eth in normalize_output(run('scope org; scope service-profile {}; sh vnic | egrep -v "Name|---|vNIC"'.format(profile_name), shell=False, quiet=True)):
                name = eth.split()[0]
                mac = mac_re.search(eth).group()
                server.add_nic(name=name, mac=mac)
            servers[server_num] = server

    return [servers[key] for key in sorted(servers.keys())]


@task
def cleanup(host='10.23.228.253', username='admin', password='cisco'):
    from fabric.api import settings, run

    with settings(host_string='{user}@{ip}'.format(user=username, ip=host), password=password, connection_attempts=50, warn_only=False):
        for profile in run('scope org; sh service-profile status | egrep -V "Service|----" | cut -f 1 -d " "', shell=False).split():
            run('scope org; delete service-profile {0}; commit-buffer'.format(profile), shell=False)
        for mac_pool in run('scope org; sh mac-pool | egrep -V "Name|----|MAC" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete mac-pool {0}; commit-buffer'.format(mac_pool), shell=False)
        for server_pool in run('scope org; sh server-pool | egrep -V "Name|----|MAC" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete server-pool {0}; commit-buffer'.format(server_pool), shell=False)
        for uuid_pool in run('scope org; sh uuid-suffix-pool | egrep -V "Name|----|UUID" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete uuid-suffix-pool {0}; commit-buffer'.format(uuid_pool), shell=False)
        for boot_policy in run('scope org; sh boot-policy | egrep -V "Name|----|UUID" | cut -f 5 -d " "', shell=False).split():
            run('scope org; delete boot-policy {0}; commit-buffer'.format(boot_policy), shell=False)
        for vlan in run('scope eth-uplink; sh vlan | eg -V "default|VLAN|Name|-----" | cut -f 5 -d " "', shell=False).split():
            run('scope eth-uplink; delete vlan {0}; commit-buffer'.format(vlan), shell=False)


@task
def configure_for_osp7(host='10.23.228.253', username='admin', password='cisco'):
    from fabric.api import settings, run

    server_pool_name = 'QA-SERVERS'
    uuid_pool_name = 'QA'
    mac_pools = {'PXE-INT': 'AA', 'MGMT': 'BB', 'eth0': 'CC', 'eth1': 'DD'}
    vlans = {'MGMT': 1723, 'PXE-INT': 111, 'eth0': 333, 'eth1': 334}
    mgmt_ips = '10.23.228.231 10.23.228.233 10.23.228.224 255.255.255.225'

    with settings(host_string='{user}@{ip}'.format(user=username, ip=host), password=password, connection_attempts=50, warn_only=False):
        server_nums = run('sh server status | egrep -V "Server|----" | cut -f 1 -d " "', shell=False).split()
        n_servers = len(server_nums)  # how many servers UCSM currently sees

        # UUID pool
        run('scope org; create uuid-suffix-pool {name}; set assignment-order sequential; create block 1234-000000000001 1234-00000000000{n}; commit-buffer'.format(
            name=uuid_pool_name, n=n_servers), shell=False)
        # Boot policy
        for card in ['PXE-EXT', 'PXE-INT']:
            run('scope org; create boot-policy {0}; set boot-mode legacy; commit-buffer'.format(card), shell=False)
            run('scope org; scope boot-policy {0}; create lan; set order 1;  create path primary; set vnic {0}; commit-buffer'.format(card), shell=False)
            run('scope org; scope boot-policy {0}; create storage; create local; create local-any; set order 2; commit-buffer'.format(card), shell=False)
        # IPMI access policy

        # MAC pools
        for mac_pool_name, mac_value in mac_pools.iteritems():
            mac_range = '00:25:B5:00:{0}:01 00:25:B5:00:{0}:{1}'.format(mac_value, n_servers)
            run('scope org; create mac-pool {0}; set assignment-order sequential; create block {1}; commit-buffer'.format(mac_pool_name, mac_range), shell=False)
        # VLANs
        for vlan_name, vlan_id in vlans.iteritems():
            run('scope eth-uplink; create vlan {0} {1}; set sharing none; commit-buffer'.format(vlan_name, vlan_id), shell=False)
        # Mgmt IPs pool
        #run('scope org; scope ip-pool ext-mgmt; set assignment-order sequential; create block {0}; commit-buffer'.format(mgmt_ips), shell=False)

        # Server pool
        run('scope org; create server-pool {0}; commit-buffer'.format(server_pool_name), shell=False)

        for server_num in server_nums:
            # add server to server pool
            run('scope org; scope server-pool {0}; create server {1}; commit-buffer'.format(server_pool_name, server_num), shell=False)
            profile = 'QA1{0}'.format(server_num)
            # service profile
            run('scope org; create service-profile {0}; set ipmi-access-profile IPMI; commit-buffer'.format(profile), shell=False)
            if server_num == '1':
                # special vNIC to have this server booted via external PXE
                run('scope org; scope service-profile {0}; create vnic PXE-EXT fabric a-b; set identity dynamic-mac 00:25:B5:11:11:11; commit-buffer'.format(profile), shell=False)
                run('scope org; scope service-profile {0}; set boot-policy PXE-EXT; commit-buffer'.format(profile), shell=False)
            else:
                run('scope org; scope service-profile {0}; set boot-policy PXE-INT; commit-buffer'.format(profile), shell=False)
            for mac_pool_name in mac_pools.keys():
                # add vNICs
                run('scope org; scope service-profile {0}; create vnic {1} fabric a-b; set identity mac-pool {1}; commit-buffer'.format(profile, mac_pool_name), shell=False)
                # add VLAN to vNIC
                run('scope org; scope service-profile {0}; scope vnic {1}; create eth-if {1}; set default-net yes; commit-buffer'.format(profile, mac_pool_name), shell=False)
                # remove default VLAN
                run('scope org; scope service-profile {0}; scope vnic {1}; delete eth-if default; commit-buffer'.format(profile, mac_pool_name), shell=False)

            # enable SoL
            # run('scope org; scope service-profile {0};  create sol-config; enable; commit-buffer'.format(profile), shell=False)

            # main step - association - here server will be rebooted
            run('scope org; scope service-profile {0}; associate server {1}; commit-buffer'.format(profile, server_num), shell=False)


@task
def ucsm(host='10.23.228.253', username='admin', password='cisco', service_profile_name='test_profile'):
    import UcsSdk

    try:
        u = UcsSdk.UcsHandle()
        u.Login(name=host, username=username, password=password)
        org = u.GetManagedObject(inMo=None, classId=UcsSdk.OrgOrg.ClassId(), params={UcsSdk.OrgOrg.LEVEL: '0'})
        u.AddManagedObject(inMo=org, classId=UcsSdk.LsServer.ClassId(), params={UcsSdk.LsServer.NAME: service_profile_name}, modifyPresent=True)
    except Exception as ex:
        print ex
    finally:
        u.Logout()


@task
def sandhya(host='10.23.228.253', username='admin', password='cisco', service_profile_name='test_profile'):
    import UcsSdk

    class Const(object):
        VNIC_PATH_PREFIX = "/vnic-"
        VLAN_PATH_PREFIX = "/if-"
        VLAN_PROFILE_PATH_PREFIX = "/net-"
        VLAN_PROFILE_NAME_PREFIX = "OS-"
        PORT_PROFILE_NAME_PREFIX = "OS-PP-"
        CLIENT_PROFILE_NAME_PREFIX = "OS-CL-"
        CLIENT_PROFILE_PATH_PREFIX = "/cl-"

        SERVICE_PROFILE_PATH_PREFIX = "org-root/ls-"
        ETH0 = "/ether-eth0"
        ETH1 = "/ether-eth1"

    const = Const()

    def make_vlan_name(vlan_id):
        return const.VLAN_PROFILE_NAME_PREFIX + str(vlan_id)

    vlan_id = 333
    service_profile = 'QA14'

    handle = UcsSdk.UcsHandle()
    handle.Login(name=host, username=username, password=password)

    service_profile_path = (const.SERVICE_PROFILE_PATH_PREFIX + str(service_profile))
    vlan_name = make_vlan_name(vlan_id)

    obj = handle.GetManagedObject(inMo=None, classId=UcsSdk.LsServer.ClassId(), params={UcsSdk.LsServer.DN: service_profile_path})
    for eth in handle.GetManagedObject(inMo=obj, classId=UcsSdk.VnicEther.ClassId(), params={}):
        vlan_path = (const.VLAN_PATH_PREFIX + vlan_name)
        eth_if = handle.AddManagedObject(inMo=eth, classId=UcsSdk.VnicEtherIf.ClassId(), modifyPresent=True, params={UcsSdk.VnicEtherIf.DN: vlan_path,
                                                                                                                     UcsSdk.VnicEtherIf.NAME: vlan_name,
                                                                                                                     UcsSdk.VnicEtherIf.DEFAULT_NET: "no"}, )

    handle.CompleteTransaction()


@task
def ucsm_backup(host='172.29.172.177', username='admin', password='cisco'):
    """Take config backup"""
    import UcsSdk

    try:
        u = UcsSdk.UcsHandle()
        u.Login(name=host, username=username, password=password)
        u.BackupUcs(type='config-all', pathPattern='./ucsm-config-all.xml')  # also possible config-system, config-logical, full-state
    finally:
        u.Logout()


@task
def restore_backup(host='172.29.172.177', username='admin', password='cisco', backup_path='lab/configs/ucsm/g10-ucsm-config.xml'):
    """Upload given xml to restore given UCSM to the state when backup was taken"""
    import UcsSdk

    try:
        u = UcsSdk.UcsHandle()
        u.Login(name=host, username=username, password=password)
        u.ImportUcsBackup(path=backup_path, merge=False, dumpXml=False)
    finally:
        u.Logout()
