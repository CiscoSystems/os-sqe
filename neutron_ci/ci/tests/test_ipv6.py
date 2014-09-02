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
# @author: Dane LeBlanc, Nikolay Fedotov, Cisco Systems, Inc.
import os
from ci import WORKSPACE

from ci.lib.test_case import BaseTestCase
from ci.lib.utils import run_cmd_line

LOCAL_CONF = '''
[[local|localrc]]
ADMIN_PASSWORD=secret
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
MYSQL_PASSWORD=nova
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,n-sch,n-novnc,n-xvnc,n-cauth,horizon,rabbit
enable_service mysql
disable_service n-net
enable_service q-svc
enable_service q-agt
enable_service q-l3
enable_service q-dhcp
enable_service q-meta
enable_service q-lbaas
enable_service neutron
enable_service tempest
NOVA_USE_NEUTRON_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
#RECLONE=no
#OFFLINE=True
RECLONE=True

TEMPEST_REPO=https://github.com/CiscoSystems/tempest.git
TEMPEST_BRANCH=ipv6
IP_VERSION=4+6
IPV6_PRIVATE_RANGE=2001:dead:beef:deed::/64
IPV6_NETWORK_GATEWAY=2001:dead:beef:deed::1
REMOVE_PUBLIC_BRIDGE=False
IPV6_PUBLIC_RANGE=2005::/64
IPV6_PUBLIC_NETWORK_GATEWAY=2005::1
'''


class IPv6Test(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        cls.devstack.local_conf = LOCAL_CONF
        cls.devstack.clone()
        cls.devstack.download_gerrit_change('refs/changes/87/87987/14')

        my_path = os.path.join(WORKSPACE, 'my')
        run_cmd_line('git clone https://github.com/kshileev/my.git {d}'
                     ''.format(d=my_path))
        cls.devstack.patch(os.path.join(my_path, 'netns.diff'))

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(
            '/opt/stack/tempest/etc/ipv6_tempests_list.txt'))
