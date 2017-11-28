from lab.test_case_worker import TestCaseWorker


class NodeDisruptor(TestCaseWorker):
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
        allowed_methods = ['reboot']

        assert self.disrupt_time > 0
        assert self.method_to_disrupt in allowed_methods, '{} not in {}, check {}'.format(self.method_to_disrupt, allowed_methods, self.test_case.path)

    def setup_worker(self):
        if self.node_to_disrupt not in self.pod.nodes_dic:
            raise RuntimeError('This pod has no node with id = "{}"'.format(self.node_to_disrupt))

    def loop_worker(self):
        import time

        node = self.pod.nodes_dic[self.node_to_disrupt]

        a = node.exe('docker ps -a --format "{{.Image}}>{{.Status}}"')
        before = {l.split()[0] for l in a.split('\n')}
        if self.method_to_disrupt == 'reboot':
            node.exe('shutdown -r now', is_warn_only=True)

        elapsed = 0
        while elapsed < self.timeout:
            a = node.exe('docker ps -a --format "{{.Image}}>{{.Status}}"', is_warn_only=True)
            if not a.failed:
                break
            elapsed += 15
            time.sleep(elapsed)

        if a.failed:
            self.fail(message='node {} did not come online in {} secs'.format(node, self.timeout), is_stop_running=True)
        after = {l.split()[0] for l in a.split('\n')}
        if after != before:
            self.fail(message='containers which are not restored: {}, status {}'.format(' '.join(before - after), ' '.join(after - before)), is_stop_running=True)

