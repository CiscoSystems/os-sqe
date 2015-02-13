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

import socket
import urlparse
import os
from ci import PARENT_FOLDER_PATH, ZUUL_URL, ZUUL_PROJECT, WORKSPACE, \
    NEXUS_VLAN_START, NEXUS_VLAN_END, BUILD_LOG_PATH, \
    NEXUS_INTF_NUM, NEXUS_IP, NEXUS_USER, NEXUS_PASSWORD, ZUUL_REF
from ci.lib.test_case import NexusTestCase


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'cisco_plugin_tests.txt')
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

enable_plugin networking-cisco https://github.com/nikolay-fedotov/networking-cisco.git ml2
enable_service cisco-ml2

LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
Q_PLUGIN=ml2
Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_nexus
Q_ML2_PLUGIN_TYPE_DRIVERS=vlan
ENABLE_TENANT_TUNNELS=False
Q_ML2_TENANT_NETWORK_TYPE=local
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
ML2_VLAN_RANGES=physnet1:{vlan_start}:{vlan_end}
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

[[post-config|/etc/neutron/ml2_conf_cisco.ini]]
[ml2_cisco]
managed_physical_network = physnet1

[ml2_mech_cisco_nexus:{router_ip}]
{host}={port}
ssh_port=22
username={username}
password={password}
'''


class ML2NexusTest(NexusTestCase):

    @classmethod
    def setUpClass(cls):
        NexusTestCase.setUpClass()

        local_conf = LOCAL_CONF.format(
            neutron_repo=urlparse.urljoin(ZUUL_URL, ZUUL_PROJECT),
            neutron_branch=ZUUL_REF,
            Q_PLUGIN_EXTRA_CONF_PATH=WORKSPACE,
            Q_PLUGIN_EXTRA_CONF_FILES=Q_PLUGIN_EXTRA_CONF_FILES,
            vlan_start=NEXUS_VLAN_START, vlan_end=NEXUS_VLAN_END,
            host=socket.gethostname(), port=NEXUS_INTF_NUM,
            router_ip=NEXUS_IP,
            username=NEXUS_USER,
            password=NEXUS_PASSWORD)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(TEST_LIST_FILE))
