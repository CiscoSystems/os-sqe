import abc
import os


class WithConfig(object):
    REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    ARTIFACTS_DIR = os.path.abspath(os.path.join(REPO_DIR, 'artifacts'))

    def __init__(self, config):
        self._exception = LabConfigError(lab_class=type(self), config=config, sample_config=self.sample_config())
        self.verify_config(sample_config=self.sample_config(), config=config)

    @abc.abstractmethod
    def sample_config(self):
        raise NotImplementedError('class {0} do not implement method sample_config()'.format(type(self)))

    def verify_config(self, sample_config, config):
        from lab.config_verificator import verify_config

        verify_config(sample_config=sample_config, config=config, exception=self._exception)

    @staticmethod
    def read_config_from_file(config_path, directory='', is_as_string=False):
        return read_config_from_file(config_path=config_path, directory=directory, is_as_string=is_as_string)

    @staticmethod
    def get_log_file_names():
        return os.path.join(WithConfig.REPO_DIR, 'iron-lady.log'), os.path.join(WithConfig.REPO_DIR, 'json.log')


CONFIG_DIR = os.path.abspath(os.path.join(WithConfig.REPO_DIR, 'configs'))
KEY_PUBLIC_PATH = os.path.abspath(os.path.join(WithConfig.REPO_DIR, 'configs', 'keys', 'public'))
KEY_PRIVATE_PATH = os.path.abspath(os.path.join(WithConfig.REPO_DIR, 'configs', 'keys', 'private'))


class LabConfigError(Exception):
    def __init__(self,  lab_class, sample_config, config, message=''):
        self.__class_name = lab_class
        self.__sample_config = sample_config
        self.__config = config
        self.__message = message
        self.__form_exception()

    @property
    def message(self):
        return self.__message

    @message.setter
    def message(self, message):
        self.__message = message
        self.__form_exception()

    def __form_exception(self):
        super(LabConfigError, self).__init__('in {klass}:\n{msg}\nSample config: {sample}\nProvided config: {provided}'.format(msg=self.__message,
                                                                                                                               klass=self.__class_name,
                                                                                                                               sample=self.__sample_config,
                                                                                                                               provided=self.__config))


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
    from lab.logger import lab_logger
    import os

    git_reference = os.getenv('SQE_GIT_REF', 'master').split('/')[-1]
    gitlab_config_repo = 'http://gitlab.cisco.com/openstack-cisco-dev/osqe-configs/raw/{0}/lab_configs/'.format(git_reference)

    if os.path.isfile(config_path):
        actual_path = config_path  # it's a full path to the local file
    else:
        actual_path = None
        for conf_dir in [CONFIG_DIR, os.path.expanduser('~/osqe-configs/lab_configs')]:
            try_this_path = os.path.join(conf_dir, directory, config_path)
            if os.path.isfile(try_this_path):
                actual_path = try_this_path
        actual_path = actual_path or gitlab_config_repo + config_path

    lab_logger.info('Taking config from {0}'.format(actual_path))
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


def ls_configs(directory=''):
    import os

    folder = os.path.abspath(os.path.join(CONFIG_DIR, directory))
    return sorted(filter(lambda name: name.endswith('.yaml'), os.listdir(folder)))


def open_artifact(name, mode):
    import os

    if not os.path.isdir(WithConfig.ARTIFACTS_DIR):
        os.makedirs(WithConfig.ARTIFACTS_DIR)
    return open(os.path.join(WithConfig.ARTIFACTS_DIR, name), mode)
