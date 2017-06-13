from lab.decorators import section


class CloudImage(object):
    IMAGES = {'sqe-iperf': 'http://172.29.173.233/cloud-images/os-sqe-localadmin-ubuntu.qcow2',
              'CSR1KV': 'http://172.29.173.233/cloud-images/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2',
              'nfvbench': 'http://172.29.173.233/cloud-images/testpmdvm-latest.qcow2'}

    SQE_PERF = 'sqe-perf'
    FOR_CSR = 'sqe-csr'

    def __init__(self, cloud, image_dic):
        self.cloud = cloud
        self._dic = image_dic

    @property
    def id(self):
        return self._dic['id']

    @property
    def name(self):
        import re

        if '(' in self._dic['name']:
            self._dic['name'], self._dic['id'] = re.findall('(.*) \((.*)\)', self._dic['name'])[0]
        return self._dic['name']

    @property
    def url(self):
        if 'url' not in self._dic:
            self._read_image_properties()
        return self._dic['url']

    @property
    def checksum(self):
        if 'checksum' not in self._dic:
            self._read_image_properties()
        return self._dic['checksum']

    @property
    def size(self):
        if 'size' not in self._dic:
            self._read_image_properties()
        return self._dic['size']

    @property
    def loc_abs_path(self):
        if 'loc_abs_path' not in self._dic:
            self._read_image_properties()
        return self._dic['loc_abs_path']

    @property
    def username(self):
        if 'username' not in self._dic:
            self._read_image_properties()
        return self._dic['username']

    @property
    def password(self):
        if 'password' not in self._dic:
            self._read_image_properties()
        return self._dic['password']

    @staticmethod
    def read_image_properties(name):
        from os import path
        import requests

        try:
            url = CloudImage.IMAGES[name]
        except KeyError:
            raise ValueError('Image "{}" is not known'.format(name))

        try:
            r = requests.get(url=url + '.txt')
            checksum, _, size, username, password = r.text.split()
            loc_abs_path = path.join('~', path.basename(url))
            return url, checksum, size, username, password, loc_abs_path
        except ValueError:
            raise ValueError('File {} has wrong body: structure'.format(url))

    def _read_image_properties(self):
        self._dic['url'], self._dic['checksum'], self._dic['size'], self._dic['username'], self._dic['password'], self._dic['loc_abs_path'] = self.read_image_properties(name=self.name)

    @staticmethod
    @section('Creating custom image')
    def create(image_name, cloud):
        image = CloudImage(cloud=cloud, image_dic={'name': image_name})

        status = cloud.os_image_show(image.name)

        if not status or status['checksum'] != image.checksum:
            cloud.mediator.r_curl(url=image.url, size=image.size, checksum=image.checksum, loc_abs_path=image.loc_abs_path)
            cloud.os_cmd('openstack image create {} --public --disk-format qcow2 --container-format bare --file {}'.format(image_name, image.loc_abs_path))
        else:
            cloud.log('image already registered in the cloud with correct checksum: {}'.format(image.checksum))
        return image.wait()

    def show(self):
        return self.cloud.os_cmd('openstack image show -f json ' + self.name, is_warn_only=True)

    def wait(self):
        import time

        while True:
            dic = self.cloud.os_cmd(cmd='openstack image show -f json ' + self.id, comment=self.name)
            if dic['status'] == 'ERROR':
                self._analyse_problem()
            elif dic['status'] == 'active':
                self.cloud.log('image={} status=active'.format(self.name))
                return self
            time.sleep(15)

    def _analyse_problem(self):
        self.cloud.r_collect_information(regex=self.id, comment='image ' + self.name + ' problem')
        raise RuntimeError('image ' + self.name + ' failed')

    @staticmethod
    @section(message='cleanup images', estimated_time=10)
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = cloud.os_cmd('openstack image list -f json')
        if not is_all:
            lst = filter(lambda x: UNIQUE_PATTERN_IN_NAME in x['Name'], lst)
        if len(lst):
            ids = [s['ID'] for s in lst]
            names = [s['Name'] for s in lst]
            cloud.os_cmd(cmd='openstack image delete ' + ' '.join(ids), comment=' '.join(names))
