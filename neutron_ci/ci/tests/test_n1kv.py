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

import os
import time
from fabric.operations import local
from ci import PARENT_FOLDER_PATH, WORKSPACE
from ci.lib.test_case import BaseTestCase


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH,
                              'cisco_n1kv_plugin_tests.txt')
UVEM_DEB = 'nexus_1000v_vem-12.04-5.2.1.SK1.3.0.135.S0-0gdb.deb'
Q_PLUGIN_EXTRA_CONF_PATH = \
    '/opt/stack/networking-cisco/etc/neutron/plugins/cisco'
Q_PLUGIN_EXTRA_CONF_FILES = 'cisco_plugins.ini'
LOCAL_CONF = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

MYSQL_PASSWORD=nova
RABBIT_PASSWORD=nova
SERVICE_TOKEN=nova
SERVICE_PASSWORD=nova
ADMIN_PASSWORD=nova
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,cinder,c-sch,c-api,c-vol,n-sch,n-novnc,n-xvnc,n-cauth,rabbit,mysql,q-svc,q-dhcp,q-meta,neutron,tempest

enable_plugin networking-cisco {net_cisco_repo} {net_cisco_ref}
enable_service net-cisco

VOLUME_BACKING_FILE_SIZE=2052M
Q_PLUGIN=cisco
declare -a Q_CISCO_PLUGIN_SUBPLUGINS=(n1kv)
Q_CISCO_PLUGIN_DEVSTACK_VSM=False
Q_CISCO_PLUGIN_VSM_IP={VSM_IP}
Q_CISCO_PLUGIN_VSM_USERNAME={VSM_LOGIN}
Q_CISCO_PLUGIN_VSM_PASSWORD={VSM_PASSWORD}
Q_CISCO_PLUGIN_UVEM_DEB_IMAGE={UVEM_DEB}
Q_CISCO_PLUGIN_INTEGRATION_BRIDGE=br-int
Q_CISCO_PLUGIN_HOST_MGMT_INTF=eth0
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
IP_VERSION=4
PHYSICAL_NETWORK=test-physnet1
LIBVIRT_FIREWALL_DRIVER=nova.virt.firewall.NoopFirewallDriver
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True

[[post-config|{Q_PLUGIN_EXTRA_CONF_PATH}/{Q_PLUGIN_EXTRA_CONF_FILES}]]
[cisco_n1k]
restrict_network_profiles = False
'''


class N1kvTest(BaseTestCase):

    vsm_ip = os.environ.get('VSM_IP')
    vsm_login = os.environ.get('VSM_LOGIN')
    vsm_password = os.environ.get('VSM_PASSWORD')

    neutron_repo = os.environ.get('NEUTRON_REPO')
    neutron_ref = os.environ.get('NEUTRON_REF')

    net_cisco_repo = os.environ.get('NET_CISCO_REPO')
    net_cisco_ref = os.environ.get('NET_CISCO_REF')

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        # reload/reset configuration of VSM
        local('sudo apt-get install -y expect')
        cmd_reload = "{script} {vsm_ip} {login} {password}".format(
            script=os.path.join(PARENT_FOLDER_PATH,
                                'files/n1kv/telnet_vsm_reload.exp'),
            vsm_ip = cls.vsm_ip, login=cls.vsm_login,
            password=cls.vsm_password)
        local(cmd_reload)
        time.sleep(60*1)

        local_conf = LOCAL_CONF.format(
            neutron_repo=cls.neutron_repo,
            neutron_branch=cls.neutron_ref,
            net_cisco_repo=cls.net_cisco_repo,
            net_cisco_ref=cls.net_cisco_ref,
            Q_PLUGIN_EXTRA_CONF_PATH=Q_PLUGIN_EXTRA_CONF_PATH,
            Q_PLUGIN_EXTRA_CONF_FILES=Q_PLUGIN_EXTRA_CONF_FILES,
            VSM_IP=cls.vsm_ip,
            VSM_LOGIN=cls.vsm_login,
            VSM_PASSWORD=cls.vsm_password,
            UVEM_DEB=os.path.join(WORKSPACE, UVEM_DEB))

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(
            test_list_path=TEST_LIST_FILE))
