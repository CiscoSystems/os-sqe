import abc
from lab.with_config import WithConfig


class Provider(WithConfig):
    @abc.abstractmethod
    def execute(self, clouds_and_servers):
        pass

    def __repr__(self):
        return u'{}'.format(type(self).__name__)
