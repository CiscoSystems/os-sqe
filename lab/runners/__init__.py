import abc
from lab import WithConfig


class Runner(WithConfig):
    @abc.abstractmethod
    def run(self, servers):
        pass
