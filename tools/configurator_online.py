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
        from lab.laboratory import Laboratory
        from lab.server import Server

        ip = Configurator.KNOWN_LABS.get(lab_name, {'mgm_ip': lab_name})['mgm_ip']
        if not validators.ipv4(ip):
            raise ValueError('"{}" is not resolved as valid IPv4'.format(ip))

        self.s = Server(ip=ip, username='root', password=None)
        for password in [None, Configurator.KNOWN_LABS['default_password'], 'cisco123']:  # first try to exe with key pair, if failed, second try with default password
            try:
                self.s.password = password
                ans = self.s.exe(cmd='ciscovim install-status # {} mgm with password {}'.format(lab_name, self.s.password), is_warn_only=True)
                if '| CEPH                   | Success |' not in ans:
                    raise RuntimeError('{} is not properly installed'.format(lab_name))
                cmd_tmpl = 'cat /root/openstack-configs/setup_data.yaml && echo separator && hostname && echo separator && grep -E "image_tag|namespace|RELEASE_TAG" /root/openstack-configs/defaults.yaml # {} mgm with password {}'
                ans = self.s.exe(cmd=cmd_tmpl.format(lab_name, self.s.password), is_warn_only=True)

                setup_data, hostname, grep = ans.split('separator')
                pod = Laboratory()
                pod.setup_data = yaml.load(setup_data)
                pod.driver = pod.setup_data['MECHANISM_DRIVERS']
                pod.name = lab_name + '-' + pod.driver
                pod.gerrit_tag = grep.split('\r\n')[2].split(':')[-1].strip()
                pod.namespace = grep.split('\r\n')[3].split(':')[-1].strip()
                pod.release_tag = grep.split('\r\n')[1].split(':')[-1].strip()
                pod.os_name = self.VIM_NUM_VS_OS_NAME_DIC[pod.release_tag.rsplit('.', 1)[0]]
                self.create_from_setup_data(pod=pod)
                if pod.driver == 'vts':
                    pod.driver_version = pod.vtc.r_vtc_get_version()
                    pod.vtc.r_vtc_get_all()
                else:
                    pod.driver_version = 'vpp XXXX'
                return pod
            except SystemExit:
                time.sleep(1)
                self.log_warning('It is potentially old release without key pair installed for root@mgm {}, trying to re-execute with default password'.format(lab_name))
                time.sleep(1)
                continue

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

        ssh_ip = None if node_id != 'mgm' else self.s.ip
        ssh_username = None if node_id != 'mgm' else self.s.username
        ssh_password = None if node_id != 'mgm' else self.s.password
        proxy = None if node_id == 'mgm' else pod.mgm

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
