import abc
from lab.WithConfig import WithConfig
from lab.WithRunMixin import WithRunMixin


class Runner(WithConfig, WithRunMixin):
    @abc.abstractmethod
    def execute(self, clouds, servers):
        pass
