# Copyright 2014 Cisco Systems, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import os
from keystoneclient.client import Client as Keystone
from glanceclient.client import Client as Glance
from fabs import lab


class OS:
    def __init__(self, ip):
        self.controller_ip = ip
        self.username = 'admin'
        self.password = 'nova'
        self.tenant_name = 'admin'
        self.auth_url = 'http://{0}:5000/v2.0/'.format(ip)

        self.keystone = Keystone(username=self.username, tenant_name=self.tenant_name, password=self.password, auth_url=self.auth_url)
        self.keystone.authenticate()
        self.glance = Glance(version='1', endpoint=self.keystone.service_catalog.url_for(service_type="image"), token=self.keystone.auth_token)

        self.image_id = None
        self.image_id_alt = None
        for image in self.glance.images.list():
            if not self.image_id:
                self.image_id = image.id
            if not self.image_id_alt:
                self.image_id_alt = image.id

    def create_tempest_conf(self):
        with open(os.path.join(lab.TOPOLOGIES_DIR, 'tempest.conf')) as f:
            template = f.read()

        with open('cisco-sqe-tempest.conf', 'w') as f:
            f.write(template.format(controller_ip=self.controller_ip, image_id=self.image_id, image_id_alt=self.image_id_alt))

    def create_openrc(self):
        with open(os.path.join(lab.TOPOLOGIES_DIR, 'openrc')) as f:
            template = f.read()

        with open('openrc', 'w') as f:
            f.write(template.format(controller_ip=self.controller_ip))
