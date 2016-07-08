from lab.worker import Worker


class VtsDisruptor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts_classes.vtc import Vtc

        possible_nodes = ['active-vtc', 'passive-vtc', 'active-dl', 'passive-dl']
        possible_methods = ['isolate-from-management', 'isolate-from-api', 'reboot-vm', 'reboot-host']
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
            cluster = self._vtc.vtc_get_cluster_info()
            active_passive = self._node_to_disrupt.split('-')[0]
            for vtc in lab.get_nodes_by_class(Vtc):
                if vtc.get_nic('a').get_ip_and_mask()[0] == cluster[active_passive]['address']:
                    self._node_to_disrupt = vtc
                    break
        if 'dl' in self._node_to_disrupt:
            active_passive = self._node_to_disrupt.split('-')[0]
            self._node_to_disrupt = self._vtc.vtc_get_xrvrs()[0 if active_passive == 'active' else -1]

    def loop(self):
        import time

        self._log.info('host={}; status=going-off {}'.format(self._vtc, self._node_to_disrupt.disrupt(start_or_stop='start', method_to_disrupt=self._method_to_disrupt)))
        time.sleep(self._downtime)
        self._log.info('host={}; status=going-on {}'.format(self._vtc, self._node_to_disrupt.disrupt(start_or_stop='stop', method_to_disrupt=self._method_to_disrupt)))
        time.sleep(self._uptime)
