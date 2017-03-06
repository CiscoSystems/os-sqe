from lab.parallelworker import ParallelWorker


class CloudDisruptor(ParallelWorker):

    def check_config(self):
        possible_nodes = ['control', 'compute']
        possible_methods = ['reboot']
        try:
            if self.node_to_disrupt not in possible_nodes:
                raise ValueError('{}: node-to-disrupt "{}" invalid. must be one of: {}'.format(self._yaml_path, self.node_to_disrupt, possible_nodes))
            if self.method_to_disrupt not in possible_methods:
                raise ValueError('{}: method-to-disrupt "{}" invalid.  must be one of: {}'.format(self._yaml_path, self.method_to_disrupt, possible_methods))
        except KeyError:
            raise ValueError('This monitor requires uptime, downtime, node-to-disrupt, method-to-disrupt {}'.format(self._yaml_path))

    @property
    def node_to_disrupt(self):
        return self._kwargs['node-to-disrupt']

    @property
    def method_to_disrupt(self):
        return self._kwargs['method-to-disrupt']

    def setup_worker(self):
        pass

    def loop_worker(self):
        import time

        self.get_cloud().os_disrupt()
        self.log('Sleeping for {} secs uptime'.format(self._kwargs['uptime']))
        time.sleep(self._kwargs['uptime'])
