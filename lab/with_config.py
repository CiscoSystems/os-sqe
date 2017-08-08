import os
import requests


class WithConfig(object):
    SQE_USERNAME = 'sqe'
    REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    ARTIFACTS_DIR = os.path.abspath(os.path.join(REPO_DIR, 'artifacts'))
    CONFIG_DIR = os.path.abspath(os.path.join(REPO_DIR, 'configs'))
    CONFIGS_REPO_URL = 'https://wwwin-gitlab-sjc.cisco.com/mercury/configs/raw/master'

    REMOTE_FILE_STORE_IP = '172.29.173.233'
    PRIVATE_KEY = requests.get(url=CONFIGS_REPO_URL + '/' + 'private.key').text
    PUBLIC_KEY = requests.get(url=CONFIGS_REPO_URL + '/' + 'public.key').text

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
    def get_list_of_pods():
        import requests
        import re

        resp = requests.get(url=WithConfig.CONFIGS_REPO_URL.replace('raw', 'tree'))
        if resp.status_code != 200:
            raise ValueError('Something wrong with repo: {}'.format(WithConfig.CONFIGS_REPO_URL))
        return re.findall('.*title="(.*)" href=.*yaml', resp.text)


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
