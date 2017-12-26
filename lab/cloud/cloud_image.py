from lab.decorators import section


class CloudImage(object):
    STATUS_ACTIVE = 'active'

    IMAGES = {'sqe-iperf': 'http://172.29.173.233/cloud-images/os-sqe-localadmin-ubuntu.qcow2',
              'sqe-csr': 'http://172.29.173.233/cloud-images/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2',
              'nfvbenchvm': 'http://172.29.173.233/cloud-images/testpmdvm-latest.qcow2'}

    SQE_PERF = 'sqe-iperf'
    FOR_CSR = 'sqe-csr'

    def __init__(self, cloud, dic):
        self.cloud = cloud
        self.img_id = dic['id']
        self.img_name = dic['name']
        self.img_checksum = dic['checksum']
        self.img_status = dic['status']
        self.img_username = None
        self.img_password = None
        if self.img_name in self.IMAGES:
            _, checksum, _, self.img_username, self.img_password = self.read_image_properties(self.img_name)

    def __repr__(self):
        return self.img_name + ' ' + self.img_status

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
        url, checksum, size, username, password = CloudImage.read_image_properties(name=image_name)
        im = filter(lambda x: x.img_name == 'image_name', cloud.images)

        if im and im[0].img_status == CloudImage.STATUS_ACTIVE and im[0].img_checksum == checksum:
            cloud.log('image already registered in the cloud with correct checksum: {}'.format(checksum))
            return im[0]

        if im:
            cloud.os_cmd(cmd='openstack image delete ' + im[0].img_id, comment=im[0].img_name)
        abs_path = cloud.mediator.r_curl(url=url, size=size, checksum=checksum)
        created = cloud.os_cmd('openstack image create {} --public --disk-format qcow2 --container-format bare --file {} '.format(image_name, abs_path))
        image = CloudImage(cloud=cloud, dic=created)
        if created['status'] == 'ERROR':
            image.analyse_problem()
        return image

    def analyse_problem(self):
        self.cloud.pod.r_collect_info(regex=self.img_id, comment='image ' + self.img_name + ' problem')
        raise RuntimeError('image ' + self.img_name + ' failed')

    @staticmethod
    @section(message='cleanup images (estimate 10 secs)')
    def img_cleanup(cloud, is_all):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME

        cmd = 'openstack image list | grep  -vE "\+|ID" {} | cut -c 3-38 | while read id; do openstack image delete $id; done'.format('| grep ' + UNIQUE_PATTERN_IN_NAME if not is_all else '')
        cloud.os_cmd([cmd])
