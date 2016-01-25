import abc
from lab.with_config import WithConfig


class Deployer(WithConfig):
    @abc.abstractmethod
    def wait_for_cloud(self, list_of_servers):
        """Make sure that cloud is up and running on the provided list of servers
        :param list_of_servers: list of server provided during provisioning phase
        """
        pass

    def verify_cloud(self, cloud, from_server):
        from lab.logger import create_logger

        log = create_logger()
        net_list = from_server.run(command='neutron net-list {cloud}'.format(cloud=cloud))
        ha_networks = {}
        for line in net_list.split('\n'):
            if 'HA network' in line:
                _, net_id, name_tenant_id, subnet_id_cdir, _ = line.split('|')
                subnet_id, _ = subnet_id_cdir.split()
                _, _, _, tenant_id = name_tenant_id.split()
                net_info = from_server.run(command='neutron net-show {subnet_id} {cloud}'.format(subnet_id=net_id, cloud=cloud))
                seg_id = filter(lambda x: 'segmentation_id' in x, net_info.split('\r\n'))[0].split('|')[-2].strip()
                ha_networks[net_id.strip()] = {'tenant_id': tenant_id, 'subnet_id': subnet_id, 'seg_id': seg_id}

        log.info('n_ha_networks={n} seg_ids={seg_ids}'.format(n=len(ha_networks), seg_ids=sorted([x['seg_id'] for x in ha_networks.itervalues()])))

        from_server.run(command='neutron port-list {cloud}'.format(cloud=cloud))
        from_server.run(command='neutron router-list {cloud}'.format(cloud=cloud))
        from_server.run(command='openstack server list {cloud}'.format(cloud=cloud))
        for service in cloud.services():
            for url in ['publicURL', 'internalURL', 'adminURL']:
                end_point = from_server.run(command='openstack catalog show {service} {cloud} | grep {url} | awk \'{{print $4}}\''.format(cloud=cloud, service=service, url=url))
                cloud.add_service_end_point(service=service, url=url, end_point=end_point)
        return cloud
