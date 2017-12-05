from lab.decorators import section


class CloudImage(object):
    IMAGES = {'sqe-iperf': 'http://172.29.173.233/cloud-images/os-sqe-localadmin-ubuntu.qcow2',
              'sqe-csr': 'http://172.29.173.233/cloud-images/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2',
              'nfvbenchvm': 'http://172.29.173.233/cloud-images/testpmdvm-latest.qcow2'}

    SQE_PERF = 'sqe-iperf'
    FOR_CSR = 'sqe-csr'

    def __init__(self, cloud, image_dic, username=None, password=None):
        self.cloud = cloud
        self.dic = image_dic
        self.username = username
        self.password = password

    @property
    def id(self):
        return self.dic['id']

    @property
    def name(self):
        import re

        if '(' in self.dic['name']:
            self.dic['name'], self.dic['id'] = re.findall('(.*) \((.*)\)', self.dic['name'])[0]
        return self.dic['name']

    @property
    def checksum(self):
        return self.dic['checksum']

    @staticmethod
    def read_image_properties(name):
        import requests

        url = CloudImage.IMAGES[name]
        url_txt = url + '.txt'

        try:
            r = requests.get(url=url_txt)
            if not r.ok:
                raise RuntimeError(r.url + ': ' + r.reason)
            checksum, _, size, username, password = r.text.split()
            return url, checksum, size, username, password
        except ValueError:
            raise ValueError(url_txt + ' has wrong body, expected checksum file_name size username password')

    @staticmethod
    @section('Creating custom image (estimate 30 sec)')
    def create(image_name, cloud):
        a = cloud.os_cmd(cmd='openstack image show -f json ' + image_name,  is_warn_only=True)
        status = {'checksum': 0, 'status': 'no'} if 'Could not find resource' in a else a

        url, checksum, size, username, password = CloudImage.read_image_properties(name=image_name)
        if status['checksum'] != checksum:
            if status['status'] != 'no':
                cloud.os_cmd(cmd='openstack image delete ' + status['id'], comment=status['name'])
            abs_path = cloud.mediator.r_curl(url=url, size=size, checksum=checksum)
            created = cloud.os_cmd('openstack image create {} --public --disk-format qcow2 --container-format bare --file {} -f json'.format(image_name, abs_path))
            image = CloudImage(cloud=cloud, image_dic=created, username=username, password=password)
            if created['status'] == 'ERROR':
                image.analyse_problem()
        else:
            image = CloudImage(cloud=cloud, image_dic=status, username=username, password=password)
            cloud.log('image already registered in the cloud with correct checksum: {}'.format(checksum))
        return image

    def analyse_problem(self):
        self.cloud.pod.r_collect_info(regex=self.id, comment='image ' + self.name + ' problem')
        raise RuntimeError('image ' + self.name + ' failed')

    @staticmethod
    @section(message='cleanup images (estimate 10 secs)')
    def cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        lst = cloud.os_cmd('openstack image list -f json')
        if not is_all:
            lst = filter(lambda x: UNIQUE_PATTERN_IN_NAME in x['Name'], lst)
        if len(lst):
            ids = [s['ID'] for s in lst]
            names = [s['Name'] for s in lst]
            cloud.os_cmd(cmd='openstack image delete ' + ' '.join(ids), comment=' '.join(names))
