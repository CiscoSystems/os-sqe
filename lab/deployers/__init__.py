import abc
from lab.WithConfig import WithConfig


class Deployer(WithConfig):
    @abc.abstractmethod
    def wait_for_cloud(self, list_of_servers):
        """Make sure that cloud is up and running on the provided list of servers
        :param list_of_servers: list of server provided during provisioning phase
        """
        pass

    def verify_cloud(self, cloud, from_server):
        from_server.run(command='neutron net-list {cloud}'.format(cloud=cloud))
        from_server.run(command='neutron subnet-list {cloud}'.format(cloud=cloud))
        from_server.run(command='neutron router-list {cloud}'.format(cloud=cloud))
        from_server.run(command='openstack server list {cloud}'.format(cloud=cloud))
        return cloud
