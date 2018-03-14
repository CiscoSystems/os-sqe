from lab.test_case_worker import TestCaseWorker


class VtsDisruptor(TestCaseWorker):
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
        possible_nodes = ['master-vtc', 'slave-vtc', 'master-vtsr', 'slave-vtsr']
        possible_methods = ['isolate-from-mx', 'isolate-from-api', 'isolate-from-t', 'libvirt-suspend', 'vm-reboot', 'corosync-stop', 'ncs-stop']

        assert self.disrupt_time > 0
        assert self.node_to_disrupt in possible_nodes, '{} not in {}, check {}'.format(self.node_to_disrupt, possible_nodes, self.test_case.path)
        if self.node_to_disrupt in ['master-vtsr', 'slave-vtsr']:
            assert self.method_to_disrupt not in ['isolate-from-api', 'isolate-from-t'], '{} for VTSR is not allowed, check {}'.format(self.method_to_disrupt, self.test_case.path)
        assert self.method_to_disrupt in possible_methods, '{} not in {}, check {}'.format(self.method_to_disrupt, possible_methods, self.test_case.path)

    def setup_worker(self):
        if len(self.pod.vts) < 2:
            raise RuntimeError('This pod has no actual HA, single host runs all VTS VMs: {}'.format(self.pod.vts[0].virtual_servers))

    def loop_worker(self):
        st1 = self.ha_status()
        node_id = st1[self.node_to_disrupt.split('-')[0]].replace('vtc', self.node_to_disrupt.split('-')[-1])
        vtc_individual = self.pod.vtc.individuals[node_id]

        if self.method_to_disrupt == 'libvirt-suspend':
            ans = vtc_individual.hard.exe(cmd='virsh list --all; virsh suspend {}; virsh list --all'.format(vtc_individual.id))
            if 'Domain {} suspended'.format(vtc_individual.id) not in ans:
                raise RuntimeError('{}: failed to suspend libivrt domain: {}'.format(self, ans))
            self.during_disruption()
            ans = vtc_individual.hard.exe(cmd='virsh resume {}; virsh list --all'.format(vtc_individual.id))
            if 'Domain {} resumed'.format(vtc_individual.id) not in ans:
                raise RuntimeError('{}: failed to suspend libvirt domain: {}'.format(self, ans))
        elif self.method_to_disrupt in ['isolate-from-mx', 'isolate-from-api']:
            api_or_mgmt = 'api' if 'api' in self.method_to_disrupt else 'mgmt'
            ans = vtc_individual.hard.exe('ip a | grep {}-{}'.format(vtc_individual.id, api_or_mgmt))
            if_name = ans.split()[1][:-1]
            ans = vtc_individual.hard.exe('ip l s dev {0} down; ip a s dev {0}'.format(if_name))
            if 'state DOWN' not in ans:
                raise RuntimeError('{}: failed to down iface: {}'.format(vtc_individual, ans))
            self.log('iface={} status=down for downtime={}'.format(if_name, self.disrupt_time))
            self.during_disruption()
            ans = vtc_individual.hard.exe('ip l s dev {0} up; ip a s dev {0}'.format(if_name))
            if 'UP' not in ans:
                raise RuntimeError('{}: failed to down iface: {}'.format(vtc_individual, ans))
            self.log('iface={} status=up after downtime={}'.format(if_name, self.disrupt_time))
        elif self.method_to_disrupt == 'vm-reboot':
            # 'set -m' because of http://stackoverflow.com/questions/8775598/start-a-background-process-with-nohup-using-fabric
            vtc_individual.exe('shutdown -r now')
        st2 = self.ha_status()
        if 'master' in self.node_to_disrupt:
            assert st1['master'] != st2['master'], 'Somehting stange VTC master is not changed'

    def ha_status(self):
        st = self.pod.vtc.r_vtc_crm_mon()
        self.log('master={} slave={} online={} offline={} when=during_disruption'.format(st['master'], st['slave'], st['online'], st['offline']))
        return st

    def during_disruption(self):
        import time

        interval = self.disrupt_time / 10
        for i in range(10):
            self.ha_status()
            time.sleep(interval)
