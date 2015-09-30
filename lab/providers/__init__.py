import abc
from lab import WithConfig


class Provider(WithConfig):
    @abc.abstractmethod
    def wait_for_servers(self):
        """Make sure that all servers in provider are indeed online"""
        pass
