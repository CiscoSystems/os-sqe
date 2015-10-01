import abc

from lab.WithConfig import WithConfig
from lab.WithRunMixin import WithRunMixin


class Deployer(WithConfig, WithRunMixin):
    @abc.abstractmethod
    def wait_for_cloud(self, list_of_servers):
        """Make sure that cloud is up and running on the provided list of servers"""
        pass

    def verify_cloud(self, cloud, from_server):
        self.run(command='neutron net-list {cloud}'.format(cloud=cloud), server=from_server)
        self.run(command='neutron subnet-list {cloud}'.format(cloud=cloud), server=from_server)
        self.run(command='neutron router-list {cloud}'.format(cloud=cloud), server=from_server)
        self.run(command='openstack server list {cloud}'.format(cloud=cloud), server=from_server)
        return cloud
