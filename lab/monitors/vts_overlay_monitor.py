from lab.worker import Worker


class VtsOverlayMonitor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts import Vts

        self._lab = self._cloud.mediator.lab()
        self._vtc = Vts(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else self._lab.get_nodes(Vts)[0]

    def loop(self):
        networks = self._cloud.list_networks()
        for network in networks:
            net_synced = self._vtc.verify_network(network)
            self._log.info('os_network={0}; synced={1}'.format(network['id'], net_synced))

            if network['subnets']:
                subnet = self._cloud.show_subnet(network['subnets'])
                subnet_synced = self._vtc.verify_subnet(network['id'], subnet)
                self._log.info('os_subnet={0}; synced={1}'.format(subnet['id'], subnet_synced))

            ports = self._cloud.list_ports(network_id=network['id'])
            ports_synced = self._vtc.verify_ports(network['id'], ports)
            self._log.info('ports={0}; synced={1}'.format(len(ports), ports_synced))

        instances = self._cloud.server_list()
        instances_synced = self._vtc.verify_instances(instances)
        self._log.info('instances={0}; synced={1}'.format(len(instances), instances_synced))

        pass
