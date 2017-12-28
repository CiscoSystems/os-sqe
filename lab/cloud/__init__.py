UNIQUE_PATTERN_IN_NAME = 'sqe-'


class CloudObject(object):
    def __init__(self, cloud, dic):
        self.cloud = cloud
        self.id = str(dic['id'])
        self.name = dic['name']
        self.role = self.__class__.__name__.replace('Cloud', '').lower()
        self.status = dic.get('status', '')

    def __repr__(self):
        return self.name + ' ' + self.status
