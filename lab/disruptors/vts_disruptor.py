from lab.parallelworker import ParallelWorker


class VtsDisruptor(ParallelWorker):
    ARG_METHOD_TO_DISRUPT = 'method_to_disrupt'
    ARG_NODE_TO_DISRUPT = 'node_to_disrupt'
    ARG_DISRUPT_TIME = 'disrupt_time'

    @property
    def disrupt_time(self):
        return self.args[self.ARG_DISRUPT_TIME]

    @property
    def node_to_disrupt(self):
        return self.args[self.ARG_NODE_TO_DISRUPT]

    @property
    def method_to_disrupt(self):
        return self.args[self.ARG_METHOD_TO_DISRUPT]

    def check_arguments(self):
        possible_nodes = ['master-vtc', 'slave-vtc', 'master-dl', 'slave-dl']
        possible_methods = ['isolate-from-mx', 'isolate-from-api', 'isolate-from-t', 'vm-shutdown', 'vm-reboot', 'corosync-stop', 'ncs-stop']

        assert self.disrupt_time > 0
        assert self.node_to_disrupt in possible_nodes
        assert self.method_to_disrupt in possible_methods

    def setup_worker(self):
        pass

    def loop_worker(self):
        import re
        import time

        node_role = self.node_to_disrupt.split('-')[0]
        node_object_to_disrupt = None

        if 'vtc' in self.node_to_disrupt:
            cluster = self.pod.vtc.r_vtc_show_ha_cluster_members()
            cluster = {x['status']: x['address'] for x in cluster['collection']['tcm:members']}
            for vtc in self.pod.vtc.individuals:
                if vtc.get_nic('a').get_ip_and_mask()[0] == cluster[node_role]:
                    node_object_to_disrupt = vtc
                    break
        elif 'dl' in self.node_to_disrupt:
            master_id = None
            xrvrs = self.pod.vtc.r_vtc_get_xrvrs()
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

        self.args.get('previously_disrupted', None)

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

        node_object_to_disrupt.disrupt(method_to_disrupt=self.method_to_disrupt, downtime=self.disrupt_time)

        self.args['previously_disrupted'] = node_object_to_disrupt.get_node_id()
