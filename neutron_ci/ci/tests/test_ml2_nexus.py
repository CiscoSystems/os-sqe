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
import os
from ci import PARENT_FOLDER_PATH, \
    NEXUS_VLAN_START, NEXUS_VLAN_END, \
    NEXUS_INTF_NUM, NEXUS_IP, NEXUS_USER, NEXUS_PASSWORD
from ci.lib.test_case import NexusTestCase


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'cisco_plugin_tests.txt')
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
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,n-sch,n-novnc,n-xvnc,rabbit
NETWORK_API_EXTENSIONS=agent,allowed-address-pairs,binding,dhcp_agent_scheduler,dvr,ext-gw-mode,external-net,extra_dhcp_opt,extraroute,l3-ha,l3_agent_scheduler,multi-provider,provider,quotas,router,security-group,service-type
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

enable_plugin networking-cisco {net_cisco_repo} {net_cisco_ref}
enable_service net-cisco

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

[[post-config|{Q_PLUGIN_EXTRA_CONF_PATH}/{Q_PLUGIN_EXTRA_CONF_FILES}]]
[ml2_cisco]
managed_physical_network = physnet1

[ml2_mech_cisco_nexus:{router_ip}]
{host}={port}
ssh_port=22
username={username}
password={password}
'''


class ML2NexusTest(NexusTestCase):

    neutron_repo = os.environ.get('NEUTRON_REPO')
    neutron_ref = os.environ.get('NEUTRON_REF')

    net_cisco_repo = os.environ.get('NET_CISCO_REPO')
    net_cisco_ref = os.environ.get('NET_CISCO_REF')

    @classmethod
    def setUpClass(cls):
        NexusTestCase.setUpClass()

        local_conf = LOCAL_CONF.format(
            neutron_repo=cls.neutron_repo,
            neutron_branch=cls.neutron_ref,
            net_cisco_repo=cls.net_cisco_repo,
            net_cisco_ref=cls.net_cisco_ref,
            Q_PLUGIN_EXTRA_CONF_PATH=Q_PLUGIN_EXTRA_CONF_PATH,
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
        self.assertFalse(self.devstack.run_tempest(
            'tempest.api.network.test_networks '
            'tempest.api.network.test_ports '
            'tempest.scenario.test_network_basic_ops '
            'tempest.scenario.test_network_advanced_server_ops'))
