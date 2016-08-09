from lab.worker import Worker


class VtsDisruptor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts_classes.vtc import Vtc

        possible_nodes = ['master-vtc', 'slave-vtc', 'active-dl', 'passive-dl']
        possible_methods = ['isolate-from-mx', 'isolate-from-api', 'vm-shutdown', 'vm-reboot', 'corosync-stop', 'ncs-stop']
        try:
            self._downtime = self._kwargs['downtime']
            self._uptime = self._kwargs['uptime']
            self._node_to_disrupt = self._kwargs['node-to-disrupt']
            self._method_to_disrupt = self._kwargs['method-to-disrupt']
            if self._node_to_disrupt not in possible_nodes:
                raise ValueError('node-to-disrupt must be  one of: {0}'.format(possible_nodes))
            if self._method_to_disrupt not in possible_methods:
                    raise ValueError('method-to-disrupt must be  one of: {0}'.format(possible_methods))
        except KeyError:
            raise ValueError('This monitor requires downtime and node-to-disrupt')
        lab = self._cloud.mediator.lab()
        self._vtc = Vtc(node_id='VtcSpecial', role='vtc', lab=None, hostname='NoDefined') if self._ip else lab.get_nodes_by_class(Vtc)[0]
        if self._ip:
            self._vtc.set_oob_creds(ip=self._ip, username=self._username, password=self._password)
        if 'vtc' in self._node_to_disrupt:
            cluster = self._vtc.r_vtc_show_ha_cluster_members()
            cluster = {x['role']: x['address'] for x in cluster}
            master_slave = self._node_to_disrupt.split('-')[0]
            for vtc in lab.get_nodes_by_class(Vtc):
                if vtc.get_nic('a').get_ip_and_mask()[0] == cluster[master_slave]:
                    self._node_to_disrupt = vtc
                    break
        elif 'dl' in self._node_to_disrupt:
            active_passive = self._node_to_disrupt.split('-')[0]
            self._node_to_disrupt = self._vtc.vtc_get_xrvrs()[0 if active_passive == 'active' else -1]

    def loop(self):
        import time

        self._log.info('host={}; status=going-off {}'.format(self._vtc, self._node_to_disrupt.disrupt(start_or_stop='start', method_to_disrupt=self._method_to_disrupt)))
        self._log.info('Sleeping for {} secs downtime'.format(self._downtime))
        time.sleep(self._downtime)
        self._log.info('host={}; status=going-on {}'.format(self._vtc, self._node_to_disrupt.disrupt(start_or_stop='stop', method_to_disrupt=self._method_to_disrupt)))
        self._log.info('Sleeping for {} secs uptime'.format(self._uptime))
        time.sleep(self._uptime)
