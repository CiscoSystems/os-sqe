from lab.worker import Worker


class XrvrNotSynced(Exception):
    pass


class XrvrMonitor(Worker):

    def setup_worker(self):
        from lab.vts_classes.vtc import Vtc
        from lab.vts_classes.xrvr import Xrvr

        self._lab = self._cloud.mediator.lab()
        self._vtc = Vtc(name='NotDefined', role='vtc', ip=self._ip, username=self._username, password=self._password, lab=None, hostname='NoDefined') if self._ip else self._lab.get_nodes(Vtc)[0]

        xrvr_nodes = self._lab.get_nodes(Xrvr)
        if len(xrvr_nodes) > 0:
            self._xrvr = xrvr_nodes[0]
        else:
            raise Exception('There is not XRVR node')

    def loop_worker(self):
        import json

        networks = self._cloud.list_networks()
        overlay_networks = self._vtc.get_overlay_networks()['items']

        xrvr_sync = True

        for network in networks:
            # Get the network and ports from VTC
            overlay_network = next(on for on in overlay_networks if on['id'] == network['id'])
            vni_number = overlay_network['vni_number']

            ports = self._cloud.list_ports(network_id=network['id'])
            for p in ports:
                port = self._cloud.show_port(p['id'])
                port_ip = json.loads(port['fixed_ips'].replace('\\', ''))['ip_address']
                mac = port['mac_address']
                vtf = self._vtc.get_vtf(port['binding:host_id'])

                host = self._xrvr.xrvr_show_host(vni_number, mac)
                if not host:
                    xrvr_sync = False
                else:
                    xrvr_sync &= host['ipv4_address'] == port_ip
                    xrvr_sync &= host['mac'].replace('.', '').lower() == mac.replace(':', '').lower()
                    xrvr_sync &= host['switch'] == str(vtf._ip)
        self._log.info('xrvr={0}; synced={1}'.format(self._xrvr._ip, xrvr_sync))
        if not xrvr_sync:
            raise XrvrNotSynced('XRVR {0} is not synced'.format(xrvr_sync))
