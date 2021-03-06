from lab.test_case_worker import TestCaseWorker


class ServersFromImageScenario(TestCaseWorker):
    STATUS_SERVER_CREATING = 'status=ServerCreating'
    STATUS_SERVER_CREATED = 'status=ServerCreated'
    STATUS_SERVER_SNAPSHOTING = 'status=ServerSnapshoting'
    STATUS_SERVER_SNAPSHOTED = 'status=ServerSnapshoted'

    ARG_MANDATORY_N_SERVERS = 'n_servers'
    ARG_MANDATORY_IMAGE = 'image'
    ARG_MANDATORY_FLAVOR = 'flavor'
    ARG_MANDATORY_UPTIME = 'uptime'

    def check_arguments(self):
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_image import CloudImage

        assert self.n_servers >= 1
        assert self.uptime > 10
        assert self.flavor in CloudFlavor.FLAVOR_TYPES.keys(), '{}: flavor "{}" is wrong, possible are {}'.format(self, self.flavor, CloudFlavor.FLAVOR_TYPES.keys())
        assert self.image in CloudImage.IMAGES.keys(), '{}: image "{}" is wrong, possible are {}'.format(self, self.image, CloudImage.IMAGES.keys())

    @property
    def n_servers(self):
        return self.args[self.ARG_MANDATORY_N_SERVERS]

    @property
    def uptime(self):
        return self.args[self.ARG_MANDATORY_UPTIME]

    @property
    def servers(self):
        return self.args['servers']

    @servers.setter
    def servers(self, servers):
        self.args['servers'] = servers

    @property
    def image(self):
        return self.args[self.ARG_MANDATORY_IMAGE]

    @image.setter
    def image(self, image):
        self.args[self.ARG_MANDATORY_IMAGE] = image

    @property
    def flavor(self):
        return self.args[self.ARG_MANDATORY_FLAVOR]

    @flavor.setter
    def flavor(self, flavor):
        self.args[self.ARG_MANDATORY_FLAVOR] = flavor

    @property
    def keypair(self):
        return self.args['keypair']

    @keypair.setter
    def keypair(self, key):
        self.args['keypair'] = key

    @property
    def sec_grp(self):
        return self.args['sec_grp']

    @sec_grp.setter
    def sec_grp(self, key):
        self.args['sec_grp'] = key

    def setup_worker(self):
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_image import CloudImage
        from lab.cloud.cloud_key_pair import CloudKeyPair
        from lab.cloud.cloud_security_group import CloudSecurityGroup

        self.log(self.STATUS_SETUP_RUNING)
        self.log('getting cloud status')

        self.log(CloudKeyPair.STATUS_KEYPAIR_CREATING)
        self.keypair = CloudKeyPair.create(cloud=self.cloud)
        self.log(CloudKeyPair.STATUS_KEYPAIR_CREATED)

        self.log(CloudImage.STATUS_IMAGE_CREATING)
        self.image = CloudImage.create(cloud=self.cloud, image_name=self.image)
        self.log(CloudImage.STATUS_IMAGE_CREATED)

        self.log(CloudFlavor.STATUS_FLAVOR_CREATING)
        self.flavor = CloudFlavor.create(cloud=self.cloud, flavor_type=self.flavor)
        self.log(CloudFlavor.STATUS_FLAVOR_CREATED)

        self.log(CloudSecurityGroup.STATUS_SECGRP_CREATING)
        self.sec_grp = CloudSecurityGroup.create(cloud=self.cloud)
        self.log(CloudSecurityGroup.STATUS_SECGRP_CREATED)

        self.log(self.STATUS_SETUP_FINISHED)

    def loop_worker(self):
        import time
        from lab.cloud.cloud_server import CloudServer

        self.log(self.STATUS_SERVER_CREATING + ' n=' + str(self.n_servers))
        self.servers = CloudServer.create(how_many=self.n_servers, flavor=self.flavor, image=self.image, on_nets=self.cloud.networks, key=self.keypair, timeout=self.timeout, cloud=self.cloud)
        self.log('Waiting 30 sec to settle servers...')
        time.sleep(30)
        self.passed(self.STATUS_SERVER_CREATED + ' n={}'.format(self.n_servers))
        if str(self.uptime) != 'forever':
            time.sleep(self.uptime)
