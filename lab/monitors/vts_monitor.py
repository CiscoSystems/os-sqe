from lab.worker import Worker


class VtsMonitor(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        from lab.vts_classes.vtc import Vtc

        lab = self._cloud.mediator.lab()
        self._vtc = Vtc(node_id='Vtc{}'.format(self._ip), role='vtc', lab=None, hostname='NoDefined') if self._ip else lab.get_nodes_by_class(Vtc)[0]
        if self._ip:
            self._vtc.set_oob_creds(ip=self._ip, username=self._username, password=self._password)
        self._vtfs = self._vtc.r_vtc_get_vtfs()
        self._xrvrs = self._vtc.r_vtc_get_xrvrs()

    def loop(self):
        self._log.info('cluster={}'.format(self._vtc.r_vtc_show_ha_cluster_members()))
