import abc
from lab.with_config import WithConfig


class Deployer(WithConfig):
    @abc.abstractmethod
    def wait_for_cloud(self, list_of_servers):
        """Make sure that cloud is up and running on the provided list of servers
        :param list_of_servers: list of server provided during provisioning phase
        """
        pass

    def __repr__(self):
        return u'{}'.format(type(self).__name__)
