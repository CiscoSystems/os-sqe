# Copyright 2014 Cisco Systems, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
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
#
# @author: Nikolay Fedotov, Cisco Systems, Inc.

import urlparse
from fabric.operations import local
import os
from ci import PARENT_FOLDER_PATH, ZUUL_URL, ZUUL_PROJECT, \
    ZUUL_REF, WORKSPACE
from ci.lib.test_case import BaseTestCase


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'tailf_ncs_tests.txt')
Q_PLUGIN_EXTRA_CONF_PATH = \
    '/opt/stack/networking-cisco/etc/neutron/plugins/ml2'
Q_PLUGIN_EXTRA_CONF_FILES = 'ml2_conf_ncs.ini'
LOCAL_CONF = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

# Only uncomment the below two lines if you are running on Fedora
disable_service heat h-api h-api-cfn h-api-cw h-eng
disable_service cinder c-sch c-api c-vol
disable_service horizon
disable_service n-cpu
enable_service n-cond
disable_service n-net
enable_service q-svc
enable_service q-dhcp
enable_service q-l3
enable_service q-meta
enable_service quantum
enable_service tempest
enable_service q-agt

enable_plugin networking-cisco {net_cisco_repo} {net_cisco_ref}
enable_service net-cisco

Q_PLUGIN=ml2
Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,ncs,logger
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})

VNCSERVER_LISTEN=0.0.0.0

HOST_NAME=$(hostname)
SERVICE_HOST_NAME=$(hostname)
HOST_IP=$(ip addr | grep inet | grep eth0 | awk -F" " '{{print $2}}'| sed -e 's/\/.*$//')
SERVICE_HOST=$(hostname)

MYSQL_HOST=$(hostname)
RABBIT_HOST=$(hostname)
GLANCE_HOSTPORT=$(hostname):9292
KEYSTONE_AUTH_HOST=$(hostname)
KEYSTONE_SERVICE_HOST=$(hostname)

MYSQL_PASSWORD=mysql
RABBIT_PASSWORD=rabbit
QPID_PASSWORD=rabbit
SERVICE_TOKEN=service
SERVICE_PASSWORD=admin
ADMIN_PASSWORD=admin

GIT_BASE=https://git.openstack.org
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True

[[post-config|{Q_PLUGIN_EXTRA_CONF_PATH}/{Q_PLUGIN_EXTRA_CONF_FILES}]]
[ml2_ncs]
url=http://127.0.0.1:8888/openstack/
username=admin
password=admin
'''


class TailFNCSTest(BaseTestCase):

    neutron_repo = os.environ.get('NEUTRON_REPO')
    neutron_ref = os.environ.get('NEUTRON_REF')

    net_cisco_repo = os.environ.get('NET_CISCO_REPO')
    net_cisco_ref = os.environ.get('NET_CISCO_REF')

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        # Install NGINX
        nginx_conf = os.path.join(PARENT_FOLDER_PATH,
                                  'files/ncs/nginx-ncs.conf')
        local('sudo apt-get install -y nginx')
        local('sudo cp {0} /etc/nginx/sites-available/default'.format(nginx_conf))
        local('sudo service nginx restart')

        local_conf = LOCAL_CONF.format(
            neutron_repo=cls.neutron_repo,
            neutron_branch=cls.neutron_ref,
            net_cisco_repo=cls.net_cisco_repo,
            net_cisco_ref=cls.net_cisco_ref,
            Q_PLUGIN_EXTRA_CONF_PATH=WORKSPACE,
            Q_PLUGIN_EXTRA_CONF_FILES=Q_PLUGIN_EXTRA_CONF_FILES)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(
            test_list_path=TEST_LIST_FILE))
