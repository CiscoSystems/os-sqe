from lab.worker import Worker


class VtsDisruptor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts import Vts

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
        self._vtc = Vts(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else lab.get_nodes(Vts)[0]

    def loop(self):
        import time

        self._log.info('host={0}; status=going-off'.format(self._vtc, self._vtc.disrupt('start')))
        time.sleep(self._downtime)
        self._log.info('host={0}; status=going-on'.format(self._vtc, self._vtc.dirupt('stop')))
        time.sleep(self._uptime)
