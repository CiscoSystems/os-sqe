import abc
from lab.WithConfig import WithConfig
from lab.WithRunMixin import WithRunMixin


class Provider(WithConfig, WithRunMixin):
    @abc.abstractmethod
    def wait_for_servers(self):
        """Make sure that all servers in provider are indeed online"""
        pass
