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

import urlparse
import os
from ci import ZUUL_URL, ZUUL_PROJECT, ZUUL_REF, NEXUS_IP, \
    NEXUS_PASSWORD, NEXUS_USER, NEXUS_INTF_NUM, NEXUS_VLAN_END, \
    NEXUS_VLAN_START, SCREEN_LOG_PATH, PARENT_FOLDER_PATH
from ci.lib.test_case import NexusTestCase


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'cisco_plugin_tests.txt')
LOCAL_CONF = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

MYSQL_PASSWORD=nova
RABBIT_PASSWORD=nova
SERVICE_TOKEN=nova
SERVICE_PASSWORD=nova
ADMIN_PASSWORD=nova
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,n-sch,n-novnc,n-xvnc,n-cauth,rabbit
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
LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
Q_PLUGIN=cisco
declare -a Q_CISCO_PLUGIN_SUBPLUGINS=(openvswitch nexus)
declare -A Q_CISCO_PLUGIN_SWITCH_INFO=([{nexus_ip}]={nexus_user}:{nexus_pass}:22:{hostname}:{nexus_intf_num})
PHYSICAL_NETWORK=physnet1
OVS_PHYSICAL_BRIDGE=br-eth1
TENANT_VLAN_RANGE={vlan_start}:{vlan_end}
ENABLE_TENANT_VLANS=True
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True
'''


class MonolithicNexusTest(NexusTestCase):

    @classmethod
    def setUpClass(cls):
        NexusTestCase.setUpClass()

        local_conf = LOCAL_CONF.format(
            neutron_repo=urlparse.urljoin(ZUUL_URL, ZUUL_PROJECT),
            neutron_branch=ZUUL_REF,
            nexus_ip=NEXUS_IP,
            nexus_user=NEXUS_USER,
            nexus_pass=NEXUS_PASSWORD,
            hostname=cls.node.hostname,
            nexus_intf_num=NEXUS_INTF_NUM,
            vlan_start=NEXUS_VLAN_START, vlan_end=NEXUS_VLAN_END,
            JOB_LOG_PATH=SCREEN_LOG_PATH)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(TEST_LIST_FILE))