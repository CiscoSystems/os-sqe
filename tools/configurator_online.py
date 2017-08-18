from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Configurator(WithConfig, WithLogMixIn):
    def sample_config(self):
        pass

    def __init__(self):
        self.s = None

    def __repr__(self):
        return u'online configurator'

    def create(self, lab_name):
        import validators
        import yaml
        import time
        from lab.server import Server

        ip = Configurator.KNOWN_LABS.get(lab_name, {'mgm_ip': lab_name})['mgm_ip']
        if not validators.ipv4(ip):
            raise ValueError('"{}" is not resolved as valid IPv4'.format(ip))

        self.s = Server(ip=ip, username='root', password=None)
        for password in [None, Configurator.DEFAULT_PASSWORD]:  # first try to exe with key pair, if failed, second try with default password
            try:
                self.s.password = password
                ans = self.s.exe(cmd='ciscovim install-status # {} mgm with password {}'.format(lab_name, self.s.password), is_warn_only=True)
                if '| CEPH                   | Success |' not in ans:
                    raise RuntimeError('{} is not properly installed'.format(lab_name))
                ans = self.s.exe(cmd='cat /root/openstack-configs/setup_data.yaml # {} mgm with password {}'.format(lab_name, self.s.password), is_warn_only=True)
                return self.create_from_setup_data(setup_data=yaml.load(ans))
            except SystemExit:
                time.sleep(1)
                self.log_warning('It is potentially old release without key pair installed for root@mgm {}, trying to re-execute with default password'.format(lab_name))
                time.sleep(1)
                continue

    def create_from_setup_data(self, setup_data):
        from lab.laboratory import Laboratory

        from tools.configurator import Configurator as ConfiguratorOffline

        pod = Laboratory()
        pod.setup_data = setup_data

        ConfiguratorOffline.process_mercury_nets(pod=pod)
        ConfiguratorOffline.process_switches(pod=pod)

        mgm_cfg = {'cimc_info': {'cimc_ip': pod.setup_data['TESTING_MGMT_NODE_CIMC_IP'],
                                 'cimc_username': pod.setup_data['TESTING_MGMT_CIMC_USERNAME'],
                                 'cimc_password': pod.setup_data['TESTING_MGMT_CIMC_PASSWORD']}}

        for node_id, node_dic in [('mgm', mgm_cfg)] + sorted(pod.setup_data['SERVERS'].items()):
            self.process_single_node(pod=pod, node_id=node_id, node_dic=node_dic)

        # ConfiguratorOffline.process_connections(pod=pod)
        # pod.validate_config()
        ConfiguratorOffline.save_self_config(p=pod)
        pod.versions = pod.mgmt.r_get_version()
        return pod

    @staticmethod
    def get_class_for_node_id(pod, node_id):
        from lab.nodes.cimc_server import CimcCompute, CimcController, CimcCeph, CimcVts
        from lab.nodes.mgmt_server import CimcDirector

        if node_id == 'mgm':
            return CimcDirector

        node_id_vs_role = {}
        for r, id_lst in pod.setup_data['ROLES'].items():
            for nid in id_lst:
                node_id_vs_role[nid] = r

        klass = {'control': CimcController, 'compute': CimcCompute, 'block_storage': CimcCeph, 'vts': CimcVts}[node_id_vs_role[node_id]]
        return klass

    def process_single_node(self, pod, node_id, node_dic):
        # from lab.network import Nic

        oob_ip = node_dic['cimc_info']['cimc_ip'],
        oob_username = node_dic['cimc_info'].get('cimc_username') or pod.setup_data['CIMC-COMMON']['cimc_username']
        oob_password = node_dic['cimc_info'].get('cimc_password') or pod.setup_data['CIMC-COMMON']['cimc_password']

        ssh_ip = None if node_id != 'mgm' else self.s.ip
        ssh_username = None if node_id != 'mgm' else self.s.username
        ssh_password = None if node_id != 'mgm' else self.s.password
        proxy = None if node_id == 'mgm' else pod.mgmt

        klass = self.get_class_for_node_id(pod=pod, node_id=node_id)
        cfg = {'id': node_id, 'role': klass.__name__, 'proxy': proxy,
               'ssh-ip': ssh_ip, 'ssh-username': ssh_username, 'ssh-password': ssh_password,
               'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password,
               'nics': []
               }

        node = klass.create_node(pod=pod, dic=cfg)
        node.r_build_online()
        pod.nodes[node.id] = node

        self.log(str(node) + ' processed\n\n')
        if node.is_vts():
            self.process_vts_virtuals(pod=pod, vts=node)

    def process_vts_virtuals(self, pod, vts):
        from lab.nodes.vtc import Vtc
        from lab.nodes.vtsr import Vtsr

        vtc_username = pod.setup_data['VTS_PARAMETERS']['VTC_SSH_USERNAME']
        vtc_password = pod.setup_data['VTS_PARAMETERS']['VTC_SSH_PASSWORD']
        vtc_ips = pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_IPS']
        vtc_vip_a = pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_VIP']
        xrvr_ips = pod.setup_data['VTS_PARAMETERS']['VTS_XRVR_MGMT_IPS']

        ans = vts.exe('virsh list')
        for line in ans.split('\r\n')[2:]:
            if 'vtc' in line:
                # vip_m = pod.setup_data['VTS_PARAMETERS']['VTS_NCS_IP']
                cfg = {'id': 'vtc' + vts.id, 'role': Vtc.__name__, 'proxy': None, 'virtual-on': vts.id,
                       'ssh-ip': vtc_vip_a, 'ssh-ip-individual': vtc_ips, 'ssh-username': vtc_username, 'ssh-password': vtc_password, 'nics': []}
                node = Vtc.create_node(pod=pod, dic=cfg)
            elif 'vtsr' in line:
                cfg = {'id': 'vtsr' + vts.id, 'role': Vtsr.__name__, 'proxy': pod.mgmt, 'virtual-on': vts.id,
                       'ssh-ip': '11.11.11.250', 'ssh-ip-individual': xrvr_ips, 'ssh-username': vtc_username, 'ssh-password': vtc_password, 'nics': []}
                node = Vtsr.create_node(pod=pod, dic=cfg)
            else:
                raise RuntimeError('{}: Unknown virtual is running {}'.format(vts, line))
            node.r_build_online()
            pod.nodes[node.id] = node
            self.log(str(node) + ' processed\n\n')
            break
