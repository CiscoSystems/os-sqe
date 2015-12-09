import abc
import os

CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'configs'))


class WithConfig(object):
    CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'configs'))

    def __init__(self, config):
        self._exception = LabConfigException(lab_class=type(self), config=config, sample_config=self.sample_config())
        self.verify_config(sample_config=self.sample_config(), config=config)

    @abc.abstractmethod
    def sample_config(self):
        raise NotImplementedError('class {0} do not implement method sample_config()'.format(type(self)))

    def verify_config(self, sample_config, config):
        from lab.config_verificator import verify_config

        verify_config(sample_config=sample_config, config=config, exception=self._exception)

    @staticmethod
    def read_config_from_file(config_path):
        return read_config_from_file(yaml_path=config_path)


class LabConfigException(Exception):
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
        super(LabConfigException, self).__init__('in {klass}:\n{msg}\nSample config: {sample}\nProvided config: {provided}'.format(msg=self.__message,
                                                                                                                                   klass=self.__class_name,
                                                                                                                                   sample=self.__sample_config,
                                                                                                                                   provided=self.__config))


def read_config_from_file(yaml_path, is_as_string=False):
    import os
    import yaml

    actual_path = yaml_path if os.path.isfile(yaml_path) else os.path.join(CONFIG_DIR, 'labs', yaml_path)
    if not os.path.isfile(actual_path):
        folder = os.path.abspath(os.path.join(CONFIG_DIR, 'labs'))
        raise IOError('{0} not found. Provide full path or choose one of:\n{1}'.format(yaml_path, '\n'.join(filter(lambda name: name.endswith('.yaml'), os.listdir(folder)))))

    with open(actual_path) as f:
        return f.read() if is_as_string else yaml.load(f)
