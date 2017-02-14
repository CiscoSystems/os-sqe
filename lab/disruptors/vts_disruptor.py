from lab.parallelworker import ParallelWorker


class VtsDisruptor(ParallelWorker):

    @staticmethod
    def check_arguments(**kwargs):
        possible_nodes = ['master-vtc', 'slave-vtc', 'master-dl', 'slave-dl']
        possible_methods = ['isolate-from-mx', 'isolate-from-api', 'isolate-from-t', 'vm-shutdown', 'vm-reboot', 'corosync-stop', 'ncs-stop']
        try:
            if kwargs['downtime'] <= 0:
                raise ValueError('downtime must be > 0')
            if kwargs['uptime'] <= 0:
                raise ValueError('uptime must be > 0')
            if kwargs['node-to-disrupt'] not in possible_nodes:
                raise ValueError('node-to-disrupt must be  one of: {0}'.format(possible_nodes))
            if kwargs['method-to-disrupt'] not in possible_methods:
                raise ValueError('{}: "{}" invalid. method-to-disrupt must be one of: {}'.format(kwargs['yaml_path'], kwargs['method-to-disrupt'], possible_methods))
        except KeyError:
            raise ValueError('This monitor requires uptime, downtime, node-to-disrupt, method-to-disrupt {}'.format(kwargs))

    def setup_worker(self, **kwargs):
        pass

    def loop_worker(self):
        import re
        import time
        from lab.nodes.vtc import Vtc

        node_role = self._kwargs['node-to-disrupt'].split('-')[0]
        node_object_to_disrupt = None

        vtc0 = self.get_lab().get_nodes_by_class(Vtc)[0]
        if 'vtc' in self._kwargs['node-to-disrupt']:
            cluster = vtc0.r_vtc_show_ha_cluster_members()
            cluster = {x['status']: x['address'] for x in cluster['collection']['tcm:members']}
            for vtc in self.get_lab().get_nodes_by_class(Vtc):
                if vtc.get_nic('a').get_ip_and_mask()[0] == cluster[node_role]:
                    node_object_to_disrupt = vtc
                    break
        elif 'dl' in self._kwargs['node-to-disrupt']:
            master_id = None
            xrvrs = vtc0.r_vtc_get_xrvrs()
            # Looking for master xrnc/xrvr
            for xrvr in xrvrs:
                r = xrvr.cmd('sudo crm_mon -1', is_xrvr=False, is_warn_only=True)
                if 'No route to host' in r:
                    continue
                started_xrnc = None
                for i in range(6, 0, -1):
                    started_xrnc = re.search(r'Started xrnc(?P<num>\d)', r)
                    if not started_xrnc and i == 1:
                        raise Exception('It looks like dl_server is not started')
                    time.sleep(10)
                master_id = 'xrvr' + started_xrnc.group('num')
                break
            # Looking for node to disrupt
            for xrvr in xrvrs:
                if (node_role == 'master' and xrvr.get_node_id() == master_id) or (node_role == 'slave' and xrvr.get_node_id() != master_id):
                    node_object_to_disrupt = xrvr
                    break

        node_object_disrupted = self._kwargs.get('previously_disrupted', None)

        # TODO: Uncomment if fixed

#         [2017 - 02 - 14 03:12:23, 238
#         ERROR] LAB - LOG: worker = VtsDisruptor: EXCEPTION
#         Traceback(most
#         recent
#         call
#         last):
#         File
#         "./lab/parallelworker.py", line
#         138, in start_worker
#         loop_output = self.loop_worker() if not self._is_debug else self.debug_output()
#
#     File
#     "./lab/disruptors/vts_disruptor.py", line
#     71, in loop_worker
#     assert node_object_disrupted.get_node_id() == node_object_to_disrupt.get_node_id()
#
#
# AssertionError

        # if node_object_disrupted:
        #     # If it started two or more times check if master node becomes slave
        #     if node_role == 'master':
        #         # On the second+ run check if current master is a former slave.
        #         assert node_object_disrupted.get_node_id() != node_object_to_disrupt.get_node_id()
        #         self.log("Current master node [{mid}] is a former slave [{sid}]".format(
        #             sid=node_object_disrupted.get_node_id(), mid=node_object_to_disrupt.get_node_id()))
        #     if node_role == 'slave':
        #         # On the second+ run check if current slave was slave in previous run.
        #         assert node_object_disrupted.get_node_id() == node_object_to_disrupt.get_node_id()
        #         self.log("Slave node [{mid}] was slave in previous run [{sid}]".format(
        #             sid=node_object_disrupted.get_node_id(), mid=node_object_to_disrupt.get_node_id()))

        node_object_to_disrupt.disrupt(method_to_disrupt=self._kwargs['method-to-disrupt'], downtime=self._kwargs['downtime'])
        self.log('Sleeping for {} secs uptime'.format(self._kwargs['uptime']))
        time.sleep(self._kwargs['uptime'])

        self._kwargs['previously_disrupted'] = node_object_to_disrupt.get_node_id()
