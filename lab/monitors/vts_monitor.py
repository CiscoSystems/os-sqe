from lab.parallelworker import ParallelWorker


class VtsMonitor(ParallelWorker):
    def __repr__(self):
        return u'worker=VtsMonitor'

    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        from lab.vts_classes.vtc import Vtc

        self._vtc = Vtc(node_id='Vtc{}'.format(self._ip), role='vtc', lab=None) if self._ip else self._lab.get_nodes_by_class(Vtc)[0]
        if self._ip:
            self._vtc.set_oob_creds(ip=self._ip, username=self._username, password=self._password)
        self._vtfs = self._vtc.r_vtc_get_vtfs()
        self._xrvrs = self._vtc.r_vtc_get_xrvrs()

    def loop_worker(self):
        self._log.info('cluster={}'.format(self._vtc.r_vtc_show_ha_cluster_members()))
        self._log.info('networks={}'.format(self._vtc.r_vtc_show_openstack_network()))
        self._log.info('subnetworks={}'.format(self._vtc.r_vtc_show_openstack_subnet()))
        self._log.info('ports={}'.format(self._vtc.r_vtc_show_openstack_port()))
