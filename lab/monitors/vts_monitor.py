from lab.worker import Worker


class VtsMonitor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts_classes.vtc import Vtc

        lab = self._cloud.mediator.lab()
        self._vtc = Vtc(node_id='Vtc{}'.format(self._ip), role='vtc', lab=None, hostname='NoDefined') if self._ip else lab.get_nodes_by_class(Vtc)[0]
        if self._ip:
            self._vtc.set_oob_creds(ip=self._ip, username=self._username, password=self._password)
        self._vtfs = self._vtc.vtc_get_vtfs()
        self._xrvrs = self._vtc.vtc_get_xrvrs()

    def loop(self):
        for vtf in self._vtfs:
            self._log.info('host={0}; vxlan={1}'.format(vtf, vtf.vtf_show_vxlan_tunnel()))

        for xrvr in self._xrvrs:
            self._log.info('host={0}; vxlan={1}'.format(xrvr, xrvr.show_running_config()))

        return {'is_success': True, 'n_exceptions': 0}
