import os


class WithConfig(object):
    REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    ARTIFACTS_DIR = os.path.abspath(os.path.join(REPO_DIR, 'artifacts'))
    CONFIG_DIR = os.path.abspath(os.path.join(REPO_DIR, 'configs'))
    REMOTE_FILE_STORE_IP = '172.29.173.233'

    def verify_config(self, sample_config, config):
        from lab.config_verificator import verify_config

        verify_config(owner=self, sample_config=sample_config, config=config)

    @staticmethod
    def read_config_from_file(config_path, directory='', is_as_string=False):
        return read_config_from_file(config_path=config_path, directory=directory, is_as_string=is_as_string)

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

        repo_tree_url = 'https://wwwin-gitlab-sjc.cisco.com/mercury/configs/tree/master'
        resp = requests.get('https://wwwin-gitlab-sjc.cisco.com/mercury/configs/tree/master')
        if resp.status_code != 200:
            raise ValueError('Something wrong with repo: {}'.format(repo_tree_url))
        return re.findall('.*title="(.*)" href=.*yaml', resp.text)


KEY_PUBLIC_PATH = os.path.abspath(os.path.join(WithConfig.REPO_DIR, 'configs', 'keys', 'public'))
KEY_PRIVATE_PATH = os.path.abspath(os.path.join(WithConfig.REPO_DIR, 'configs', 'keys', 'private'))


def read_config_from_file(config_path, directory='', is_as_string=False):
    """ Trying to read a configuration file in the following order:
        1. try to interpret config_path as local file system full path
        2. try to interpret config_path as short file name with respect to CONFIG_DIR + directory
        2. the same as in 2 but in a local clone of osqe-configs repo
        5. if all fail, try to get it from remote osqe-configs
        :param config_path: path to the config file or just a name of the config file
        :param directory: sub-directory of CONFIG_DIR
        :param is_as_string: if True return the body of file as a string , if not interpret the file as yaml and return a dictionary
    """
    import yaml
    import requests
    import validators
    from lab.with_log import lab_logger
    import os

    git_reference = os.getenv('SQE_GIT_REF', 'master').split('/')[-1]
    gitlab_config_repo = 'https://wwwin-gitlab-sjc.cisco.com/mercury/configs/raw/{}/'.format(git_reference)

    if os.path.isfile(os.path.expanduser(config_path)):
        actual_path = os.path.abspath(os.path.expanduser(config_path))  # path to existing local file
    else:
        actual_path = None
        for conf_dir in [WithConfig.CONFIG_DIR, os.path.expanduser('~/repo/osqe-configs/lab_configs')]:
            try_this_path = os.path.abspath(os.path.join(conf_dir, directory, config_path))
            if os.path.isfile(try_this_path):
                actual_path = try_this_path
        actual_path = actual_path or gitlab_config_repo + config_path

    lab_logger.debug('Taking config from {0}'.format(actual_path))
    if validators.url(actual_path):
        resp = requests.get(actual_path)
        if resp.status_code != 200:
            raise ValueError('File is not available at this URL: {0}'.format(actual_path))
        body_or_yaml = yaml.load(resp.text)
    else:
        with open(actual_path) as f:
            body_or_yaml = f.read() if is_as_string else yaml.load(f)
    if not body_or_yaml:
        raise ValueError('{0} is empty!'.format(actual_path))

    return body_or_yaml
