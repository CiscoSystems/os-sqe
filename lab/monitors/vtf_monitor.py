from lab.worker import Worker


class VtfNotSynced(Exception):
    pass


class VtfMonitor(Worker):

    def setup(self):
        from lab.vts_classes.vtc import Vtc

        self._lab = self._cloud.mediator.lab()
        self._vtc = Vtc(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else self._lab.get_nodes_by_class(Vtc)[0]

    def loop(self):
        # List of networks defined in OpenStack
        networks = self._cloud.list_networks()

        # <vtf_ip> : True/False
        vtf_sync = {}

        for network in networks:
            # Get the network and ports from VTC
            overlay_network = self._vtc.get_overlay_network(network['id'])
            overlay_ports = self._vtc.get_overlay_network_ports(network_id=network['id'])['items']

            vni_number = overlay_network['vni_number']

            # VTFs involved in processing traffic of the <network>
            vtfs = []
            for op in overlay_ports:
                vtfs.append(self._vtc.get_vtf(op['binding_host_id']))
            vtf_ips = [vtf._ip for vtf in vtfs]

            # Verify tunnels are set up between all VTFs
            for vtf in vtfs:
                vtf_sync[str(vtf._ip)] = True
                tunnels_raw = vtf.show_vxlan_tunnel()
                for vtf_ip in vtf_ips:
                    if vtf_ip == vtf._ip:
                        continue
                    tunnel_str = '{src} (src) {dst} (dst) vni {vni} ' \
                                 'encap_fib_index 0 decap_next l2'.format(src=vtf._ip, dst=vtf_ip, vni=vni_number)
                    vtf_sync[str(vtf._ip)] &= any([tunnel_str in tunnel_raw for tunnel_raw in tunnels_raw])

        for vtf_ip, sync in vtf_sync.items():
            self._log.info('vtf={0}; sync={1}'.format(vtf_ip, sync))
            if not sync:
                raise VtfNotSynced("VTF {0} is not synced".format(vtf_ip))

        return vtf_sync