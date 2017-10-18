import os
import requests


class WithConfig(object):
    SQE_USERNAME = 'sqe'
    REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    ARTIFACTS_DIR = os.path.abspath(os.path.join(REPO_DIR, 'artifacts'))
    CONFIG_DIR = os.path.abspath(os.path.join(REPO_DIR, 'configs'))
    CONFIGS_REPO_URL = 'https://wwwin-gitlab-sjc.cisco.com/mercury/configs/raw/master'

    PRIVATE_KEY = requests.get(url=CONFIGS_REPO_URL + '/' + 'private.key').text
    PUBLIC_KEY = requests.get(url=CONFIGS_REPO_URL + '/' + 'public.key').text

    VIM_NUM_VS_OS_NAME_DIC = {'2.3': 'master', '2.2': 'newton', '2.1': 'newton', '2.0': 'newton', '1.0': 'liberty', '9.9': 'fake'}

    def verify_config(self, sample_config, config):
        from lab.config_verificator import verify_config

        verify_config(owner=self, sample_config=sample_config, config=config)

    @staticmethod
    def read_config_from_file(config_path, directory='', is_as_string=False):
        return read_config_from_file(cfg_path=config_path, folder=directory, is_as_string=is_as_string)

    @staticmethod
    def get_log_file_names():
        if not os.path.isdir(WithConfig.ARTIFACTS_DIR):
            os.makedirs(WithConfig.ARTIFACTS_DIR)
        return os.path.join(WithConfig.ARTIFACTS_DIR, 'sqe.log'), os.path.join(WithConfig.ARTIFACTS_DIR, 'json.log')

    @staticmethod
    def ls_configs(directory=''):
        folder = os.path.abspath(os.path.join(WithConfig.CONFIG_DIR, directory))
        return sorted(filter(lambda name: name.endswith('.yaml'), os.listdir(folder)))

    @staticmethod
    def open_artifact(name, mode):
        return open(WithConfig.get_artifact_file_path(short_name=name), mode)

    @staticmethod
    def is_artifact_exists(name):
        import os

        return os.path.isfile(WithConfig.get_artifact_file_path(short_name=name))

    @staticmethod
    def get_artifact_file_path(short_name):
        if not os.path.isdir(WithConfig.ARTIFACTS_DIR):
            os.makedirs(WithConfig.ARTIFACTS_DIR)

        return os.path.join(WithConfig.ARTIFACTS_DIR, short_name)

    @staticmethod
    def get_remote_store_file_to_artifacts(path):
        from fabric.api import local
        import os

        loc = path.split('/')[-1]
        local('test -e {a}/{l} || curl -s -R http://{ip}/{p} -o {a}/{l}'.format(a=WithConfig.ARTIFACTS_DIR, l=loc, ip=WithConfig.REMOTE_FILE_STORE_IP, p=path))
        return os.path.join(WithConfig.ARTIFACTS_DIR, loc)

    @staticmethod
    def save_self_config(p):
        import json
        from lab.nodes.virtual_server import VirtualServer
        from lab.nodes.lab_server import LabServer

        def net_yaml_body(net):
            return '{{id: {:3}, vlan: {:4}, cidr: {:19}, is-via-tor: {:5}, roles: {}}}'.format(net.id, net.vlan, net.net.cidr, 'True' if net.is_via_tor else 'False', net.roles_must_present)

        def nic_yaml_body(nic):
            return '{{id: {:3}, ip: {:20}, is-ssh: {:6} }}'.format(nic.id, nic.ip, nic.is_ssh)

        def node_yaml_body(node):
            a = ' {{id: {:8}, hard: "{:25}", role: {:15}, proxy: {:5}'.format(node.id, node.hardware, node.role, node.proxy.id if node.proxy is not None else None)
            a += ', oob-ip: {:15}, oob-username: {:9}, oob-password: {:9}'.format(node.oob_ip, node.oob_username, node.oob_password)
            a += ', ssh-ip: {:15}, ssh-username: {:9}, ssh-password: {:9} '.format(node.ssh_ip, node.ssh_username, node.ssh_password) if isinstance(node, LabServer) else ''
            a += ', virtual-on: {:5}, '.format(node.hard.id) if node.is_virtual() else ''
            a += ' }'
            return a

        def wire_yaml_body(wire):
            a1 = 'pc-id: {:>15}, '.format(wire.pc_id)
            a2 = 'node1: {:>5}, port1: {:>45}, mac: "{:17}", '.format(wire.n1, wire.port_id1, wire.mac)
            a3 = 'node2: {:>5}, port2: {:>20}'.format(wire.n2, wire.port_id2)
            return '{' + a1 + a2 + a3 + ' }'

        with WithConfig.open_artifact('{}.yaml'.format(p), 'w') as f:
            f.write('name: {} # any string to be used on logging\n'.format(p))
            f.write('description-url: "{}"\n'.format(p))
            f.write('gerrit_tag: ' + str(p.gerrit_tag) + '\n')
            f.write('namespace: ' + str(p.namespace) + '\n')
            f.write('release_tag: ' + str(p.release_tag) + '\n')
            f.write('os_code_name: ' + str(p.os_code_name) + '\n')
            f.write('driver: ' + str(p.driver) + '\n')
            f.write('driver_version: ' + str(p.driver_version) + '\n')
            f.write('\n')

            f.write('specials: [\n')
            special_bodies = [node_yaml_body(node=x) for x in [p.oob] + [p.tor] if x]
            f.write(',\n'.join(special_bodies))
            f.write('\n]\n\n')

            f.write('networks: [\n')
            net_bodies = [net_yaml_body(net=x) for x in p.networks.values()]
            f.write(',\n'.join(net_bodies))
            f.write('\n]\n\n')

            f.write('switches: [\n')
            switch_bodies = [node_yaml_body(node=x) for x in p.vim_tors + [p.vim_cat] if x]
            f.write(',\n'.join(switch_bodies))
            f.write('\n]\n\n')

            f.write('nodes: [\n')
            node_bodies = sorted([node_yaml_body(node=x) for x in p.nodes.values() if isinstance(x, LabServer) and not isinstance(x, VirtualServer)])
            f.write(',\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('virtuals: [\n')
            node_bodies = [node_yaml_body(node=x) for x in p.nodes.values() if isinstance(x, VirtualServer)]
            f.write(',\n'.join(node_bodies))
            f.write('\n]\n\n')

            f.write('wires: [\n')

            n1_id = ''
            for w in sorted(p.wires, key=lambda e: e.n1.id + e.port_id1):
                if w.n1.id != n1_id:
                    n1_id = w.n1.id
                    f.write('\n')
                f.write(wire_yaml_body(wire=w) + ',\n')
            f.write('\n]\n')

            if p.setup_data:
                f.write('\nsetup-data: {}'.format(json.dumps(p.setup_data, indent=4)))


def read_config_from_file(cfg_path, folder='', is_as_string=False):
    """ Trying to read a configuration file in the following order:
        1. try to interpret config_path as local fs path
        2. try to interpret config_path as local fs relative to repo/configs/directory
        2. the same as in 2 but in a local clone of configs repo
        5. if all fail, try to get it from remote WithConfig.CONFIGS_REPO_URL
        :param cfg_path: path to the config file or just a name of the config file
        :param folder: sub-folder of WirConfig.CONFIG_DIR
        :param is_as_string: if True return the body of file as a string , if not interpret the file as yaml and return a dictionary
    """
    import yaml
    import requests
    from lab.with_log import lab_logger
    from os import path

    actual_path = None
    for try_path in [cfg_path, path.join(WithConfig.CONFIG_DIR, folder, cfg_path), path.join('~/repo/mercury/configs', cfg_path)]:
        try_path = path.expanduser(try_path)
        if os.path.isfile(try_path):
            actual_path = try_path
            break

    if actual_path is None:
        actual_path = WithConfig.CONFIGS_REPO_URL + '/' + cfg_path
        resp = requests.get(url=actual_path)
        if resp.status_code != 200:
            raise ValueError('File is not available at this URL: {0}'.format(actual_path))
        cfg_txt = resp.text
    else:
        with open(actual_path) as f:
            cfg_txt = f.read()
    if not cfg_txt:
        raise ValueError('{0} is empty!'.format(actual_path))

    lab_logger.debug('CFG taken from {}'.format(actual_path))

    return cfg_txt if is_as_string else yaml.load(cfg_txt)
