def start(lab, log, args):
    is_ha_details = args.get('show-details', True)
    unique_pattern_in_name = args.get('unique_pattern_in_name', 'sqe-test')

    cloud = lab.cloud

    nets = cloud.list_networks()

    if is_ha_details:
        d = {'HA': {'ids': [], 'vlans': []},
             unique_pattern_in_name: {'ids': [], 'vlans': []}}
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
        for net_class, values in d.iteritems():
            message += 'n_{net_class}_nets={n} ids_{net_class}={ids} vlans_{net_class}={vlans} '.format(net_class=net_class,
                                                                                                        n=len(values['ids']),
                                                                                                        ids=values['ids'],
                                                                                                        vlans=values['vlans'])
    else:
        message = 'n_nets={n}'.format(n=len(nets))

    log.info(message)
