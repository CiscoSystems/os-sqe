import abc
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Runner(WithConfig, WithLogMixIn):
    @abc.abstractmethod
    def execute(self, clouds, servers):
        pass

    def __repr__(self):
        return u'{}'.format(type(self).__name__)
