import abc
from lab.with_config import WithConfig


class Runner(WithConfig):
    @abc.abstractmethod
    def execute(self, clouds, servers):
        pass

    def __repr__(self):
        return u'{}'.format(type(self).__name__)
