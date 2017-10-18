import json
import requests
from lab.with_config import WithConfig
from lab.network import Network
from lab.mercury.nodes import MercuryMgm, MercuryController, MercuryCompute, MercuryCeph, MercuryVts
from lab.nodes.others import Oob, VimTor, VimCat, Tor, UnknownN9
from lab.nodes.vtc import Vtc, VtcIndividual
from lab.nodes.xrvr import Xrvr
from lab.nodes.vtsr import Vtsr, VtsrIndividual


class WithMercury(object):

    NETWORKS_DIC = {
        'a': Network(net_id='a', cidr='10.10.10.0/24', vlan=9999, is_via_tor=True,  pod='api', roles_must_present=[MercuryMgm, MercuryController, Vtc, MercuryVts]),
        'm': Network(net_id='m', cidr='11.11.11.0/24', vlan=2011, is_via_tor=False, pod='management', roles_must_present=[MercuryMgm, MercuryController, MercuryCompute, MercuryCeph, MercuryCompute, Vtc, Xrvr, Vtsr, MercuryVts]),
        't': Network(net_id='t', cidr='22.22.22.0/24', vlan=2022, is_via_tor=False, pod='tenant', roles_must_present=[MercuryCompute, Xrvr, Vtsr, MercuryVts]),
        's': Network(net_id='s', cidr='33.33.33.0/24', vlan=2033, is_via_tor=False, pod='storage', roles_must_present=[MercuryController, MercuryCompute, MercuryCeph]),
        'e': Network(net_id='e', cidr='44.44.44.0/24', vlan=2044, is_via_tor=False, pod='external', roles_must_present=[MercuryController]),
        'p': Network(net_id='p', cidr='55.55.55.0/24', vlan=2055, is_via_tor=False, pod='provision', roles_must_present=[MercuryCompute])
    }

    MERCURY_DIC = json.loads(requests.get(url=WithConfig.CONFIGS_REPO_URL + '/mercury.json').text)
    ROLE_ID_TO_CLASS_DIC = {x.__name__: x for x in [MercuryMgm, MercuryVts, MercuryCeph, MercuryCompute, MercuryController, Vtc, VtcIndividual, Vtsr, VtsrIndividual, Tor, VimTor, VimCat, Oob, UnknownN9]}

    @staticmethod
    def mercury_node_class(pod, node_id):

        if node_id == 'mgm':
            return MercuryMgm

        node_id_vs_role = {}
        for r, id_lst in pod.setup_data_dic['ROLES'].items():
            if type(id_lst) is not list:
                continue
            for nid in id_lst:
                node_id_vs_role[nid] = r

        klass = [node_id_vs_role[node_id]]
        return klass

    @staticmethod
    def create(lab_name, is_interactive=False):
        import validators
        import yaml
        import time
        from lab.laboratory import Laboratory
        from lab.server import Server

        ip = WithMercury.MERCURY_DIC.get(lab_name, {'mgm_ip': lab_name})['mgm_ip']
        if not validators.ipv4(ip):
            raise ValueError('"{}" is not resolved as valid IPv4'.format(ip))

        ans = ''
        mgm = Server(ip=ip, username='root', password=None)
        separator = 'separator'
        for password in [None, WithMercury.MERCURY_DIC['default_password'], 'cisco123']:  # first try to exe with key pair, if failed, second try with default password
            mgm.password = password
            cmds = ['ciscovim install-status', 'cat /root/openstack-configs/setup_data.yaml', 'hostname', 'grep -E "image_tag|namespace|RELEASE_TAG" /root/openstack-configs/defaults.yaml']
            cmd = ' && echo {} && '.format(separator).join(cmds)
            ans = mgm.exe(cmd=cmd, is_warn_only=True)
            if 'Stages' in ans:
                break
            time.sleep(1)
            time.sleep(1)

        if not is_interactive and '| CEPH                   | Success |' not in ans:
            raise RuntimeError('{} is not properly installed'.format(lab_name))

        _, setup_data_text, hostname, grep = ans.split(separator)
        setup_data_dic = yaml.load(setup_data_text)
        pod = Laboratory(name=lab_name,
                         driver=setup_data_dic['MECHANISM_DRIVERS'],
                         release_tag=grep.split('\r\n')[1].split(':')[-1].strip(),
                         gerrit_tag=grep.split('\r\n')[2].split(':')[-1].strip(),
                         namespace=grep.split('\r\n')[3].split(':')[-1].strip(),
                         setup_data_dic=setup_data_dic)
        WithMercury.create_from_setup_data(pod=pod, mgm=mgm, is_interactive=is_interactive)
        if pod.driver == 'vts':
            pod.driver_version = pod.vtc.r_vtc_get_version()
            pod.vtc.r_vtc_get_all()
        else:
            pod.driver_version = 'vpp XXXX'
        return pod

    @staticmethod
    def create_from_setup_data(pod, mgm, is_interactive):
        from lab.nodes.vtc import Vtc

        WithMercury.process_nets(pod=pod)
        WithMercury.process_switches(pod=pod)

        if pod.driver == 'vts':
            cfg = {'id': 'vtc', 'role': Vtc.__name__,
                   'ssh-ip': pod.setup_data_dic['VTS_PARAMETERS']['VTS_VTC_API_VIP'],
                   'ssh-username': pod.setup_data_dic['VTS_PARAMETERS']['VTC_SSH_USERNAME'],
                   'ssh-password': pod.setup_data_dic['VTS_PARAMETERS']['VTC_SSH_PASSWORD'],
                   'vtc-username': pod.setup_data_dic['VTS_PARAMETERS']['VTS_USERNAME'],
                   'vtc-password': pod.setup_data_dic['VTS_PARAMETERS']['VTS_PASSWORD']
                   }
            pod.vtc = Vtc.create_node(pod=pod, dic=cfg)

        mgm_cfg = {'management_ip': mgm.ip, 'ssh_username': mgm.username, 'ssh_password': mgm.password,
                   'cimc_info': {'cimc_ip': pod.setup_data_dic['TESTING_MGMT_NODE_CIMC_IP'],
                                 'cimc_username': pod.setup_data_dic['TESTING_MGMT_CIMC_USERNAME'],
                                 'cimc_password': pod.setup_data_dic['TESTING_MGMT_CIMC_PASSWORD']}}

        node_id_vs_node_class = {'mgm': MercuryMgm}
        for role_name, node_names_lst in pod.setup_data_dic['ROLES'].items():
            for node_name in node_names_lst:
                node_id_vs_node_class[node_name] = {'control': MercuryController, 'compute': MercuryCompute, 'storage': MercuryCeph, 'vts': MercuryVts}[role_name]

        for node_id, node_dic in [('mgm', mgm_cfg)] + sorted(pod.setup_data_dic['SERVERS'].items()):
            cfg = {'id': node_id,
                   'role': node_id_vs_node_class[node_id].__name__,
                   'proxy': None if node_id == 'mgm' else pod.mgm,
                   'ssh-ip': node_dic.get('management_ip'),
                   'ssh-username': None if node_id != 'mgm' else node_dic['ssh_username'],
                   'ssh-password': None if node_id != 'mgm' else node_dic['ssh_password'],
                   'oob-ip': node_dic['cimc_info']['cimc_ip'],
                   'oob-username': node_dic['cimc_info'].get('cimc_username') or pod.setup_data_dic['CIMC-COMMON']['cimc_username'],
                   'oob-password': node_dic['cimc_info'].get('cimc_password') or pod.setup_data_dic['CIMC-COMMON']['cimc_password'],
                   'nics': []
                   }

            node = node_id_vs_node_class[node_id].create_node(pod=pod, dic=cfg)
            if type(node) == MercuryController:
                pod.controls.append(node)
            elif type(node) == MercuryCompute:
                pod.computes.append(node)
            elif type(node) == MercuryCeph:
                pod.cephs.append(node)
            elif type(node) == MercuryMgm:
                pod.mgm = node
            elif type(node) == MercuryVts:
                pod.vts.append(node)

        pod.controls[0].cimc_deduce_wiring_by_lldp(pod=pod)
        if is_interactive:
            map(lambda x: x.n9_validate(), pod.vim_tors)
        map(lambda x: x.r_build_online(), pod.cimc_servers_dic.values())
        map(lambda x: WithMercury.process_vts_virtuals(pod=pod, vts=x), pod.vts)
        # pod.validate_config()
        pod.save_self_config(p=pod)

    @staticmethod
    def process_vts_virtuals(pod, vts):
        import re

        num = re.findall('\d{1,3}', vts.id)[0]

        dic = {'proxy': None, 'virtual-on': vts.id,
               'ssh-username': pod.setup_data_dic['VTS_PARAMETERS']['VTC_SSH_USERNAME'],
               'ssh-password': pod.setup_data_dic['VTS_PARAMETERS']['VTC_SSH_PASSWORD'], 'nics': []}

        ans = vts.exe('virsh list')
        for virsh_vm in ans.split('\r\n')[2:]:
            if 'vtsr' in virsh_vm:
                dic['role'] = VtsrIndividual.__name__
                dic['id'] = 'vtsr' + num
                dic['ssh-ip'] = pod.setup_data_dic['VTS_PARAMETERS']['VTS_XRVR_MGMT_IPS'][int(num)-1]
                dic['proxy'] = pod.mgm
            elif 'vtc' in virsh_vm:
                dic['role'] = VtcIndividual.__name__
                dic['id'] = 'vtc' + num
                dic['ssh-ip'] = pod.setup_data_dic['VTS_PARAMETERS']['VTS_VTC_API_IPS'][int(num)-1]
            else:
                raise RuntimeError('Not known virsh VM runnning: ' + virsh_vm)
            node = VtcIndividual.create_node(pod=pod, dic=dic)
            node.r_build_online()
            pod.virtuals.append(node)
            pod.vtc.individuals[node.id] = node
            pod.log(str(node) + ' processed\n\n')
            break

    @staticmethod
    def process_nets(pod):
        from lab.network import Network
        from netaddr import IPNetwork

        for one_letter_net_id, net in sorted(WithMercury.NETWORKS_DIC.items()):
            net_mercury_cfg = filter(lambda k: k['segments'][0] == net.pod, pod.setup_data_dic['NETWORKING']['networks'])
            if net_mercury_cfg:
                cidr = net_mercury_cfg[0].get('subnet')
                vlan_id = net_mercury_cfg[0].get('vlan_id')
                if vlan_id not in [None, 'None', 'none']:
                    net.vlan = vlan_id
                if cidr:
                    net.net = IPNetwork(cidr)
                    net.is_via_tor = cidr[:2] not in ['11', '22', '33', '44', '55']
                elif vlan_id in WithMercury.MERCURY_DIC['networks']:  # some vlan ids might be known from networks assignment, so use it if such vlan_id specified while cidr is not
                    net.net = IPNetwork(WithMercury.MERCURY_DIC['networks'][vlan_id])

        pod.networks.update(Network.add_networks(pod=pod, nets_cfg=[{'id': x.id, 'vlan': x.vlan, 'cidr': x.net.cidr, 'roles': x.roles_must_present, 'is-via-tor': x.is_via_tor} for x in WithMercury.NETWORKS_DIC.values()]))

    @staticmethod
    def process_switches(pod):
        from lab.nodes.others import UnknownN9, VimTor
        from lab.wire import Wire

        known_info = WithMercury.MERCURY_DIC[pod.name.rsplit('-', 1)[0]]
        switches = []
        username, password = None, None
        for sw in pod.setup_data_dic['TORSWITCHINFO']['SWITCHDETAILS']:
            username, password = sw['username'], sw['password']
            switches.append({'id': 'n' + sw['hostname'][-1].lower(), 'role': 'VimTor', 'oob-ip': sw['ssh_ip'], 'oob-username': username, 'oob-password': password})

        if 'nc' in known_info:
            switches.append({'id': 'nc', 'role': 'VimCat', 'oob-ip': known_info['nc'], 'oob-username': username, 'oob-password': password})

        pod.vim_tors = VimTor.create_nodes(pod=pod, node_dics_lst=switches)

        wires_cfg = []
        for n9 in pod.vim_tors:
            for nei in n9.neighbours_cdp:
                if nei.port_id == 'mgmt0':
                    node2_id = 'oob'
                    if node2_id not in pod.nodes_dic:
                        pod.oob = Oob.create_node(pod=pod, dic={'id': 'oob', 'role': 'Oob', 'oob-ip': nei.ipv4, 'oob-username': 'openstack-readonly', 'oob-password': password})
                else:
                    s = filter(lambda y: y.oob_ip == nei.ipv4, pod.vim_tors)
                    if s:  # this is peer link connection
                        node2_id = s[0].id
                    else:  # this is unknown connection, one of them is connection to TOR
                        port_desc = n9.ports[nei.port_id].name
                        if 'uplink' in port_desc:
                            node2_id = 'tor'
                            if node2_id not in pod.nodes_dic:
                                pod.tor = Tor.create_node(pod=pod, dic={'id': node2_id, 'role': Tor.__name__, 'oob-ip': nei.ipv4, 'oob-username': 'openstack-read', 'oob-password': password})
                        else:
                            node2_id = nei.ipv4
                            if node2_id not in pod.nodes_dic:
                                pod.unknowns = UnknownN9.create_node(pod=pod, dic={'id': node2_id, 'role': UnknownN9.__name__, 'oob-ip': nei.ipv4, 'oob-username': 'XXXXXX', 'oob-password': password})
                wires_cfg.append({'node1': n9.id, 'port1': nei.port_id, 'mac': None, 'node2': node2_id, 'port2': nei.peer_port_id, 'pc-id': nei.pc_id})

        pod.wires.extend(Wire.add_wires(pod=pod, wires_cfg=wires_cfg))
