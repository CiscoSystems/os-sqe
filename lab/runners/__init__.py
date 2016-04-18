import abc
from lab.with_config import WithConfig


class Runner(WithConfig):
    @abc.abstractmethod
    def execute(self, clouds, servers):
        pass
