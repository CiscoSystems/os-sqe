class CloudObject(object):
    UNIQUE_PATTERN_IN_NAME = 'sqe-'

    def __init__(self, cloud, dic):
        self.cloud = cloud
        self.id = str(dic.get('id', ''))
        self.name = dic['name']
        self.role = self.__class__.__name__.replace('Cloud', '').lower()
        self.status = dic.get('status', '')
        if self.role == 'keypair':
            self.cloud.keypairs.append(self)
        elif self.role == 'flavor':
            self.cloud.flavors.append(self)
        elif self.role == 'network':
            self.cloud.nets.append(self)
        elif self.role == 'subnet':
            self.net = filter(lambda x: x.id == dic['network_id'], self.cloud.nets)[0]
            self.net.subnets.append(self)
            self.cloud.subnets.append(self)
        elif self.role == 'port':
            self.cloud.ports.append(self)
            self.net = filter(lambda x: x.id == dic['network_id'], self.cloud.nets)[0]
            self.net.ports.append(self)
        elif self.role == 'image':
            self.cloud.images.append(self)
        elif self.role == 'server':
            self.cloud.servers.append(self)
        else:
            raise RuntimeError('{}: add role to this if!'.format(self))

    def __repr__(self):
        return self.name + ' ' + self.status
