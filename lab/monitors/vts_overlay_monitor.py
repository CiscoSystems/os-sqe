from lab.parallelworker import ParallelWorker


class VtsNetworksNotSynced(Exception):
    pass


class VtsSubnetsNotSynced(Exception):
    pass


class VtsPortsNotSynced(Exception):
    pass


class VtsInstancesNotSynced(Exception):
    pass


class VtsOverlayMonitor(ParallelWorker):

    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        from lab.vts_classes.vtc import Vtc

        self._vtc = Vtc(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else self._lab.get_nodes_by_class(Vtc)[0]

    def loop_worker(self):
        networks = self._cloud.os_network_list()
        for network in networks:
            net_synced = self._vtc.verify_network(network)
            self._log.info('os_network={0}; synced={1}'.format(network['id'], net_synced))
            if not net_synced:
                raise VtsNetworksNotSynced('Network {0} is not synced'.format(network['id']))

            if network['subnets']:
                subnet = self._cloud.show_subnet(network['subnets'])
                subnet_synced = self._vtc.verify_subnet(network['id'], subnet)
                self._log.info('os_subnet={0}; synced={1}'.format(subnet['id'], subnet_synced))
                if not subnet_synced:
                    raise VtsSubnetsNotSynced('Subnet {0} is not synced'.format(subnet['id']))

            ports = self._cloud.list_ports(network_id=network['id'])
            ports_synced = self._vtc.verify_ports(network['id'], ports)
            self._log.info('os_network={0}; ports={1}; synced={2}'.format(
                network['id'], len(ports), ports_synced))
            if not ports_synced:
                raise VtsPortsNotSynced('{0} Ports of a network {0} are not synced'.format(len(ports), network['id']))

        instances = self._cloud.server_list()
        instances_synced = self._vtc.verify_instances(instances)
        self._log.info('instances={0}; synced={1}'.format(len(instances), instances_synced))
        if not instances_synced:
            raise VtsInstancesNotSynced('{0} instances not synced'.format(len(instances)))
