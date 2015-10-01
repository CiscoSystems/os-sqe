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
