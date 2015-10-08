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
                              'cisco_n1kv_ml2_driver_tests.txt')
UVEM_DEB = 'nexus_1000v_vem-12.04-5.2.1.SK1.3.0.135.S0-0gdb.deb'
Q_PLUGIN_EXTRA_CONF_PATH = \
    '/opt/stack/networking-cisco/etc/neutron/plugins/ml2'
Q_PLUGIN_EXTRA_CONF_FILES = 'ml2_conf_cisco.ini'
LOCAL_CONF = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

MYSQL_PASSWORD=nova
RABBIT_PASSWORD=nova
SERVICE_TOKEN=nova
SERVICE_PASSWORD=nova
ADMIN_PASSWORD=nova
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,cinder,c-sch,c-api,c-vol,n-sch,n-novnc,n-xvnc,rabbit,mysql,q-svc,q-dhcp,q-meta,neutron,tempest

enable_plugin networking-cisco {net_cisco_repo} {net_cisco_ref}
enable_service net-cisco

NOVA_USE_QUANTUM_API=v2
Q_PLUGIN=ml2
Q_ML2_PLUGIN_MECHANISM_DRIVERS=cisco_n1kv
Q_ML2_PLUGIN_TYPE_DRIVERS=vlan
Q_ML2_TENANT_NETWORK_TYPE=vlan
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
IP_VERSION=4
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True


# Following section is to configure N1KV mechanism driver
[[post-config|/etc/neutron/plugins/ml2/ml2_conf.ini]]
[ml2_type_vlan]
# Section to populate VLAN type driver options.
# network_vlan_ranges=<physical_network_name>:<vlan_start_range>:<vlan_end_range>
network_vlan_ranges=physnet1:100:1000

[ml2]
# Configure N1KV specific extension driver to load Policy Profiles.
extension_drivers=cisco_n1kv_ext


[[post-config|{Q_PLUGIN_EXTRA_CONF_PATH}/{Q_PLUGIN_EXTRA_CONF_FILES}]]
[ml2_cisco_n1kv]
# Section to configure Cisco N1KV VSM
n1kv_vsm_ips = {VSM_IP}
username = {VSM_LOGIN}
password = {VSM_PASSWORD}

[[post-config|/etc/neutron/neutron.conf]]
[DEFAULT]
# Configure service plugins for L3 and to fetch Cisco Policy Profiles.
service_plugins=networking_cisco.plugins.ml2.drivers.cisco.n1kv.policy_profile_service.PolicyProfilePlugin,router
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
