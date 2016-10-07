from lab.parallelworker import ParallelWorker


class CloudMonitor(ParallelWorker):
    # noinspection PyAttributeOutsideInit
    def setup_worker(self, **kwargs):
        self._is_ha_details = kwargs.get('show-details', True)

    def loop_worker(self):
        nets = self._cloud.os_network_list()

        if self._is_ha_details:
            d = {'HA': {'ids': [], 'vlans': []}}
            a = {'ids': [], 'vlans': []}
            for net in nets:
                net_id = net['id']
                vlan = net['provider:segmentation_id']
                a['ids'].append(net_id)
                a['vlans'].append(vlan)
                for net_class in d.keys():
                    if net['name'].startswith(net_class):
                        d[net_class]['ids'].append(net_id)
                        d[net_class]['vlans'].append(vlan)

            message = 'n_nets={n} vlans={vlans} ids={ids} '.format(n=len(a['ids']), ids=a['ids'], vlans=a['vlans'])
            for net_class, values in d.items():
                message += 'n_{net_class}_nets={n} ids_{net_class}={ids} vlans_{net_class}={vlans} '.format(net_class=net_class, n=len(values['ids']), ids=values['ids'], vlans=values['vlans'])
        else:
            message = 'n_nets={n}'.format(n=len(nets))

        self._log.info(message)
