from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Configurator(WithConfig, WithLogMixIn):
    def sample_config(self):
        pass

    def __init__(self):
        super(Configurator, self).__init__()

    def create(self):
        import os
        from fabric.operations import prompt

        def chunks(l, n):
            for i in range(0, len(l), n):
                yield ' * '.join(l[i:i + n])

        repo_dir = os.path.expanduser('~/repo/mercury/mercury/testbeds')
        pods = filter(lambda x: not x.startswith('.'), os.listdir(repo_dir))

        pods_str = '\n'.join(chunks(pods, 10))

        def is_pod(n):
            if n in pods:
                return os.path.join(repo_dir, n)
            else:
                raise Exception('pod {} not found'.format(n))

        pod_dir = prompt(text='Choose one of\n' + pods_str + ' > ', validate=is_pod, default='g7-2')
        yaml_names = os.listdir(pod_dir)
        yaml_name = prompt(text='Chosse one of\n{} >'.format(' '.join(yaml_names)), default=yaml_names[-1])
        setup_data = self.read_config_from_file(os.path.join(pod_dir, yaml_name))
        return self.create_from_setup_data(setup_data=setup_data)

    def create_from_setup_data(self, setup_data):
        pod = Laboratory()
        pod.setup_data = setup_data

        self.process_mercury_nets(pod=pod)
        self.process_switches(pod=pod)
        self.process_mercury_nodes(pod=pod)
        self.process_connections(pod=pod)
        pod.validate_config()
        self.save_self_config(p=pod)
        return pod

    @staticmethod
    def ask_ip_u_p(msg, default):
        from fabric.operations import prompt
        import validators

        def is_ipv4(ip):
            if ip is not None and validators.ipv4(ip):
                return ip
            else:
                raise Exception('{} is not valid ipv4'.format(ip))

        ipv4 = prompt(text=msg + ' enter IP> ', default=default, validate=is_ipv4)
        if ipv4 is None:
            return None, None, None
        username = prompt(text=msg + ' enter username > ', default='admin')
        password = prompt(text=msg + ' enter password > ')
        return ipv4, username, password

    @staticmethod
    def process_mercury_nodes(pod):
        from lab.nodes import LabNode
        from lab.nodes.virtual_server import VirtualServer

        cimc_username = pod.setup_data['CIMC-COMMON']['cimc_username']
        cimc_password = pod.setup_data['CIMC-COMMON']['cimc_password']
        username = pod.setup_data['COBBLER']['admin_username']

        nodes = [{'id': 'mgm', 'role': 'CimcDirector',
                  'oob-ip': pod.setup_data['TESTING_MGMT_NODE_CIMC_IP'], 'oob-username': pod.setup_data['TESTING_MGMT_CIMC_USERNAME'], 'oob-password': pod.setup_data['TESTING_MGMT_CIMC_PASSWORD'],
                  'ssh-username': username, 'ssh-password': None, 'proxy': None,
                  'nics': [{'id': 'a', 'ip': pod.setup_data['TESTING_MGMT_NODE_API_IP'].split('/')[0], 'is-ssh': True},
                           {'id': 'm', 'ip': pod.setup_data['TESTING_MGMT_NODE_MGMT_IP'].split('/')[0], 'is-ssh': False}]}]

        virtuals = []

        for mercury_role_id, mercury_node_ids in pod.setup_data['ROLES'].items():
            sqe_role_id = {'control': 'CimcController', 'compute': 'CimcCompute', 'block_storage': 'CimcCeph', 'vts': 'VtsHost'}[mercury_role_id]

            nets_for_this_role = {mercury_net_id: net for mercury_net_id, net in Configurator.NETWORKS.items() if sqe_role_id in net.roles_must_present}

            for i, node_id in enumerate(mercury_node_ids, start=1):
                try:
                    mercury_srv_cfg = pod.setup_data['SERVERS'][node_id]
                    oob_ip = mercury_srv_cfg['cimc_info']['cimc_ip']
                    oob_username = mercury_srv_cfg['cimc_info'].get('cimc_username', cimc_username)
                    oob_password = mercury_srv_cfg['cimc_info'].get('cimc_password', cimc_password)

                    nics = []
                    for mercury_net_id, net in nets_for_this_role.items():
                        ip_base = {'control': 10, 'compute': 20, 'ceph': 30, 'vts': 40}[mercury_role_id] if net.is_via_tor else 4
                        ip = mercury_srv_cfg.get(mercury_net_id + '_ip', str(net.get_ip_for_index(ip_base + i)))
                        nics.append({'id': mercury_net_id[0], 'ip': ip, 'is-ssh': mercury_net_id == 'management'})

                    nodes.append({'id': node_id, 'role': sqe_role_id, 'oob-ip': oob_ip, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': username, 'proxy': 'mgm', 'nics': nics})

                    if mercury_role_id == 'vts':
                        vtc_nics = [{'id': 'a', 'ip': pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_IPS'][i-1], 'is-ssh': True},
                                    {'id': 'm', 'ip': pod.setup_data['VTS_PARAMETERS']['VTS_VTC_MGMT_IPS'][i-1], 'is-ssh': False}]
                        xrvr_nics = [{'id': 'm', 'ip': pod.setup_data['VTS_PARAMETERS']['VTS_XRNC_MGMT_IPS'][i-1], 'is-ssh': True},
                                     {'id': 't', 'ip': pod.setup_data['VTS_PARAMETERS']['VTS_XRNC_TENANT_IPS'][i-1], 'is-ssh': False}]

                        virtuals.append({'id': 'vtc' + str(i), 'role': 'vtc', 'oob-ip': None, 'oob-username': None, 'oob-password': None,
                                         'ssh-username': pod.setup_data['VTS_PARAMETERS']['VTC_SSH_USERNAME'], 'ssh-password': pod.setup_data['VTS_PARAMETERS']['VTC_SSH_PASSWORD'],
                                         'virtual-on': node_id, 'vip_a': pod.setup_data['VTS_PARAMETERS']['VTS_VTC_API_VIP'], 'vip_m': pod.setup_data['VTS_PARAMETERS']['VTS_NCS_IP'], 'proxy': None, 'nics': vtc_nics})
                        virtuals.append({'id': 'xrvr' + str(i), 'role': 'xrvr', 'oob-ip': None, 'oob-username': oob_username, 'oob-password': oob_password, 'ssh-username': username, 'ssh-password': Configurator.DEFAULT_PASSWORD,
                                         'virtual-on': node_id, 'proxy': 'mgm', 'nics': xrvr_nics})
                except KeyError as ex:
                    raise KeyError('{}: no {}'.format(node_id, ex))

        pod.nodes.update(LabNode.create_nodes(pod=pod, node_dics_lst=nodes))
        pod.nodes.update(VirtualServer.create_nodes(pod=pod, node_dics_lst=virtuals))

