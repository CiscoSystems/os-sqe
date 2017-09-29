from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Configurator(WithConfig, WithLogMixIn):
    def sample_config(self):
        pass

    def __init__(self, mgm, is_interactive):
        self.mgm = mgm
        self.is_interactive = is_interactive

    def __repr__(self):
        return u'online configurator'

    @staticmethod
    def create(lab_name, is_interactive=False):
        import validators
        import yaml
        import time
        from lab.laboratory import Laboratory
        from lab.server import Server
        from lab.tims import Tims

        ip = Configurator.KNOWN_LABS.get(lab_name, {'mgm_ip': lab_name})['mgm_ip']
        if not validators.ipv4(ip):
            raise ValueError('"{}" is not resolved as valid IPv4'.format(ip))

        ans = ''
        cfg = Configurator(mgm=Server(ip=ip, username='root', password=None), is_interactive=is_interactive)
        separator = 'separator'
        for password in [None, Configurator.KNOWN_LABS['default_password'], 'cisco123']:  # first try to exe with key pair, if failed, second try with default password
            cfg.log('Trying to connect to {} with password {}...'.format(lab_name, password))
            cfg.mgm.password = password
            cmds = ['ciscovim install-status', 'cat /root/openstack-configs/setup_data.yaml', 'hostname', 'grep -E "image_tag|namespace|RELEASE_TAG" /root/openstack-configs/defaults.yaml']
            cmd = ' && echo {} && '.format(separator).join(cmds)
            ans = cfg.mgm.exe(cmd=cmd, is_warn_only=True)
            if 'Stages' in ans:
                break
            time.sleep(1)
            cfg.log_warning('It is potentially old release without key pair installed for root@mgm {}, trying to re-execute with password'.format(lab_name))
            time.sleep(1)

        if is_interactive == False and '| CEPH                   | Success |' not in ans:
            raise RuntimeError('{} is not properly installed'.format(lab_name))

        _, setup_data_text, hostname, grep = ans.split(separator)
        setup_data = yaml.load(setup_data_text)
        pod = Laboratory(name = lab_name,
                         driver = setup_data['MECHANISM_DRIVERS'],
                         release_tag=grep.split('\r\n')[1].split(':')[-1].strip(),
                         gerrit_tag=grep.split('\r\n')[2].split(':')[-1].strip(),
                         namespace=grep.split('\r\n')[3].split(':')[-1].strip(),
                         setup_data=setup_data)
        cfg.create_from_setup_data(pod=pod)
        if pod.driver == 'vts':
            pod.driver_version = pod.vtc.r_vtc_get_version()
            pod.vtc.r_vtc_get_all()
        else:
            pod.driver_version = 'vpp XXXX'
        return pod

    def create_from_setup_data(self, pod):
        from tools.configurator import Configurator as ConfiguratorOffline
        from lab.nodes.vtc import Vtc

        ConfiguratorOffline.process_mercury_nets(pod=pod)
        ConfiguratorOffline.process_switches(pod=pod)

        mgm_cfg = {'cimc_info': {'cimc_ip': pod.setup_data['TESTING_MGMT_NODE_CIMC_IP'],
                                 'cimc_username': pod.setup_data['TESTING_MGMT_CIMC_USERNAME'],
                                 'cimc_password': pod.setup_data['TESTING_MGMT_CIMC_PASSWORD']}}

        if pod.driver == 'vts':
            cfg = {'id': 'vtc', 'role': Vtc.__name__,
                   'ssh-ip': pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_VIP'],
                   'ssh-username': pod.setup_data['VTS_PARAMETERS']['VTC_SSH_USERNAME'],
                   'ssh-password': pod.setup_data['VTS_PARAMETERS']['VTC_SSH_PASSWORD'],
                   'vtc-username': pod.setup_data['VTS_PARAMETERS']['VTS_USERNAME'],
                   'vtc-password': pod.setup_data['VTS_PARAMETERS']['VTS_PASSWORD']
                   }
            pod.nodes['vtc'] = Vtc.create_node(pod=pod, dic=cfg)

        for node_id, node_dic in [('mgm', mgm_cfg)] + sorted(pod.setup_data['SERVERS'].items()):
            self.process_single_node(pod=pod, node_id=node_id, node_dic=node_dic)

        ConfiguratorOffline.process_connections(pod=pod)
        if self.is_interactive:
            map(lambda x: x.n9_validate(), pod.vim_tors)
        map(lambda x: x.r_build_online(), pod.cimc_servers)
        map(lambda x: self.process_vts_virtuals(pod=pod, vts=x), pod.vts)
        # pod.validate_config()
        ConfiguratorOffline.save_self_config(p=pod)

    @staticmethod
    def get_class_for_node_id(pod, node_id):
        from lab.nodes.cimc_server import CimcCompute, CimcController, CimcCeph, CimcVts
        from lab.nodes.mgmt_server import CimcDirector

        if node_id == 'mgm':
            return CimcDirector

        node_id_vs_role = {}
        for r, id_lst in pod.setup_data['ROLES'].items():
            if type(id_lst) is not list:
                continue
            for nid in id_lst:
                node_id_vs_role[nid] = r

        klass = {'control': CimcController, 'compute': CimcCompute, 'block_storage': CimcCeph, 'vts': CimcVts}[node_id_vs_role[node_id]]
        return klass

    def process_single_node(self, pod, node_id, node_dic):
        # from lab.network import Nic

        oob_ip = node_dic['cimc_info']['cimc_ip']
        oob_username = node_dic['cimc_info'].get('cimc_username') or pod.setup_data['CIMC-COMMON']['cimc_username']
        oob_password = node_dic['cimc_info'].get('cimc_password') or pod.setup_data['CIMC-COMMON']['cimc_password']

        ssh_ip = node_dic.get('management_ip') if node_id != 'mgm' else self.mgm.ip
        ssh_username = None if node_id != 'mgm' else self.mgm.username
        ssh_password = None if node_id != 'mgm' else self.mgm.password
        proxy = None if node_id == 'mgm' else pod.mgm

        klass = self.get_class_for_node_id(pod=pod, node_id=node_id)
        cfg = {'id': node_id, 'role': klass.__name__, 'proxy': proxy,
               'ssh-ip': ssh_ip, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
               'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password,
               'nics': []
               }

        node = klass.create_node(pod=pod, dic=cfg)
        pod.nodes[node.id] = node

    def process_vts_virtuals(self, pod, vts):
        import re
        from lab.nodes.virtual_server import VtcIndividual, VtsrIndividual

        num = re.findall('\d{1,3}', vts.id)[0]

        dic = {'proxy': None, 'virtual-on': vts.id,
               'ssh-username': pod.setup_data['VTS_PARAMETERS']['VTC_SSH_USERNAME'],
               'ssh-password': pod.setup_data['VTS_PARAMETERS']['VTC_SSH_PASSWORD'], 'nics': []}

        ans = vts.exe('virsh list')
        for virsh_vm in ans.split('\r\n')[2:]:
            if 'vtsr' in virsh_vm:
                dic['role'] = VtsrIndividual.__name__
                dic['id'] = 'vtsr' + num
                dic['ssh-ip'] = pod.setup_data['VTS_PARAMETERS']['VTS_XRVR_MGMT_IPS'][int(num)-1]
                dic['proxy'] = pod.mgm
            elif 'vtc' in virsh_vm:
                dic['role'] = VtcIndividual.__name__
                dic['id'] = 'vtc' + num
                dic['ssh-ip'] = pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_IPS'][int(num)-1]
            else:
                raise RuntimeError('Not known virsh VM runnning: ' + virsh_vm)
            node = VtcIndividual.create_node(pod=pod, dic=dic)
            node.r_build_online()
            pod.nodes[node.id] = node
            pod.vtc.individuals[node.id] = node
            self.log(str(node) + ' processed\n\n')
            break
