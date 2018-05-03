from lab.cloud import CloudObject


class CloudImage(CloudObject):
    STATUS_ACTIVE = 'active'
    STATUS_IMAGE_CREATING = 'status=ImageCreating'
    STATUS_IMAGE_CREATED = 'status=ImageCreated'

    IMAGES = {'sqe-iperf': 'http://172.29.173.233/cloud-images/os-sqe-localadmin-ubuntu.qcow2',
              'sqe-csr': 'http://172.29.173.233/cloud-images/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2',
              'nfvbenchvm': 'http://172.29.173.233/cloud-images/testpmdvm-latest.qcow2'}

    SQE_PERF = 'sqe-iperf'
    FOR_CSR = 'sqe-csr'

    def __init__(self, cloud, dic):
        super(CloudImage, self).__init__(cloud=cloud, dic=dic)
        if self.name in self.IMAGES:
            _, checksum, _, self.username, self.password = CloudImage.read_image_properties(name=self.name)
            if self.status != self.STATUS_ACTIVE or self.checksum != checksum:
                cloud.os_cmd(cmds=['openstack image delete ' + self.id], comment=self.name)

    @property
    def checksum(self):
        return self.dic_from_os['checksum']

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
    def create(image_name, cloud):
        url, checksum, size, username, password = CloudImage.read_image_properties(name=image_name)
        im = filter(lambda x: x.name == image_name, cloud.images)

        if im:
            cloud.log('image already registered in the cloud with correct checksum: {}'.format(checksum))
            return im[0]

        abs_path = cloud.mediator.r_curl(url=url, size=size, checksum=checksum)
        image = CloudImage(cloud=cloud, dic=cloud.os_cmd(['openstack image create {} --public --disk-format qcow2 --container-format bare --file {} -f json'.format(image_name, abs_path)])[0])
        if image.status == 'ERROR':
            image.analyse_problem()
        return image

    def analyse_problem(self):
        self.cloud.pod.r_collect_info(regex=self.id, comment='image ' + self.name + ' problem')
        raise RuntimeError('image ' + self.name + ' failed')
