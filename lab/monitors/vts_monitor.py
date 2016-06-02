from lab.worker import Worker


class VtsMonitor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts import Vts

        lab = self._cloud.mediator.lab()
        self._vtc = Vts(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else lab.get_nodes(Vts)[0]
        self._vtfs = self._vtc.get_vtfs()

    def loop(self):
        for vtf in self._vtfs:
            self._log.info('host={0}; vxlan={1}'.format(vtf, vtf.cmd('show vxlan tunnel')))
