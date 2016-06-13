from lab.worker import Worker


class VtsMonitor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts_classes.vtc import Vts

        lab = self._cloud.mediator.lab()
        self._vtc = Vts(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else lab.get_nodes_by_class(Vts)[0]
        self._vtfs = self._vtc.check_vtfs()
        self._xrvrs = self._vtc.check_xrvr()

    def loop(self):
        for vtf in self._vtfs:
            self._log.info('host={0}; vxlan={1}'.format(vtf, vtf.show_vxlan_tunnel()))

        for xrvr in self._xrvrs:
            self._log.info('host={0}; vxlan={1}'.format(xrvr, xrvr.show_running_config()))
