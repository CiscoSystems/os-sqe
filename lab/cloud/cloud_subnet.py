from lab.cloud import CloudObject


class CloudSubnet(CloudObject):
    STATUS_ACTIVE = 'ACTIVE'

    def __init__(self, cloud, dic):
        super(CloudSubnet, self).__init__(cloud=cloud, dic=dic)
        self.cidr = dic['cidr']
        if cloud:
            self.net = filter(lambda x: x.id == dic['network_id'], self.cloud.networks)[0]
            self.net.subnets.append(self)
        self.gateway_ip = dic.get('gateway_ip') or dic.get('gateway-ip')
        self.allocation_pool = dic.get('allocation_pools') or (dic.get('allocation-pools')[0]['start'] + '-' + dic.get('allocation-pools')[0]['end'])
