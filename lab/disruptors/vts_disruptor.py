from lab.parallelworker import ParallelWorker


class VtsDisruptor(ParallelWorker):

    def __init__(self, cloud, lab, **kwargs):
        super(VtsDisruptor, self).__init__(cloud=cloud, lab=lab, **kwargs)

        possible_nodes = ['master-vtc', 'slave-vtc', 'master-dl', 'slave-dl']
        possible_methods = ['isolate-from-mx', 'isolate-from-api', 'vm-shutdown', 'vm-reboot', 'corosync-stop', 'ncs-stop']
        try:
            self._downtime = self._kwargs['downtime']
            self._uptime = self._kwargs['uptime']
            self._node_to_disrupt = self._kwargs['node-to-disrupt']
            self._check_master_node_failover = self._kwargs.get('check_master_node_failover', False)
            self._node_object_to_disrupt = None
            self._node_object_disrupted = None
            self._method_to_disrupt = self._kwargs['method-to-disrupt']
            if self._node_to_disrupt not in possible_nodes:
                raise ValueError('node-to-disrupt must be  one of: {0}'.format(possible_nodes))
            if self._method_to_disrupt not in possible_methods:
                raise ValueError('method-to-disrupt must be  one of: {0}'.format(possible_methods))
        except KeyError:
            raise ValueError('This monitor requires downtime and node-to-disrupt')

    def __repr__(self):
        return u'worker=VtsDisruptor'

    def setup_worker(self):
        pass

    def loop_worker(self):
        import re
        import time
        from lab.vts_classes.vtc import Vtc

        node_role = self._node_to_disrupt.split('-')[0]
        self._node_object_to_disrupt = None

        vtc0 = self._lab.get_nodes_by_class(Vtc)[0]
        if 'vtc' in self._node_to_disrupt:
            cluster = vtc0.r_vtc_show_ha_cluster_members()
            cluster = {x['status']: x['address'] for x in cluster['collection']['tcm:members']}
            for vtc in self._lab.get_nodes_by_class(Vtc):
                if vtc.get_nic('a').get_ip_and_mask()[0] == cluster[node_role]:
                    self._node_object_to_disrupt = vtc
                    break
        elif 'dl' in self._node_to_disrupt:
            master_id = None
            xrvrs = vtc0.r_vtc_get_xrvrs()
            # Looking for master xrnc/xrvr
            for xrvr in xrvrs:
                r = xrvr.cmd('sudo crm_mon -1', is_xrvr=False, is_warn_only=True)
                if 'No route to host' in r:
                    continue
                master_id = 'xrvr' + re.search(r'Started xrnc(?P<num>\d)', r).group('num')
                break
            # Looking for node to disrupt
            for xrvr in xrvrs:
                if (node_role == 'master' and xrvr.get_id() == master_id) or (node_role == 'slave' and xrvr.get_id() != master_id):
                    self._node_object_to_disrupt = xrvr
                    break

        if self._check_master_node_failover and self._node_object_disrupted:
            # If it started two or more times check if master node becomes slave
            if node_role == 'master':
                # On the second+ run check if current master is a former slave.
                assert self._node_object_disrupted.get_id() != self._node_object_to_disrupt.get_id()
                self._log.debug("Current master node [{mid}] is a former slave [{sid}]".format(
                    sid=self._node_object_disrupted.get_id(), mid=self._node_object_to_disrupt.get_id()))
            if node_role == 'slave':
                # On the second+ run check if current slave was slave in previous run.
                assert self._node_object_disrupted.get_id() == self._node_object_to_disrupt.get_id()
                self._log.debug("Slave node [{mid}] was slave in previous run [{sid}]".format(
                    sid=self._node_object_disrupted.get_id(), mid=self._node_object_to_disrupt.get_id()))

        #self._log.info('host={} method={} status=going-off {}'.format(self._node_to_disrupt, self._method_to_disrupt, ''))
        self._log.info('host={} method={} status=going-off {}'.format(self._node_to_disrupt, self._method_to_disrupt, self._node_object_to_disrupt.disrupt(method_to_disrupt=self._method_to_disrupt, downtime=self._downtime)))
        self._log.info('Sleeping for {} secs uptime'.format(self._uptime))
        time.sleep(self._uptime)

        self._node_object_disrupted = self._node_object_to_disrupt
