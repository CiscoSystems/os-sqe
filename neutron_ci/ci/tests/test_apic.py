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
    NEXUS_VLAN_START, NEXUS_VLAN_END, ZUUL_REF, NEXUS_INTF_NUM
from ci.lib.test_case import BaseTestCase
from ci.lib.utils import clear_apic_config


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'cisco_apic_tests.txt')
APIC_CONF_FILES = 'ml2_apic.ini'
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
disable_service horizon
enable_service q-svc
enable_service q-agt
enable_service q-l3
enable_service q-dhcp
enable_service q-meta
enable_service neutron
enable_service tempest
LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
IPV6_ENABLED=False
Q_PLUGIN=ml2
Q_ML2_TENANT_NETWORK_TYPE=vlan
Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_apic
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
ML2_VLAN_RANGES=physnet1:{vlan_start}:{vlan_end}
NCCLIENT_REPO=git://github.com/CiscoSystems/ncclient.git
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

[[post-config|$NEUTRON_CONF]]
[keystone_authtoken]
admin_tenant_name = admin
admin_user = admin
admin_password = nova
'''

ML2_APIC_INI = '''
[ml2_cisco_apic]

# Hostname for the APIC controller
apic_host={APIC_HOST}

# Username for the APIC controller
apic_username={APIC_USER}

# Password for the APIC controller
apic_password={APIC_PASSWORD}

# Port for the APIC Controller
apic_port={APIC_PORT}

# New style config: Hostnames and ports
apic_hosts={APIC_HOST}:{APIC_PORT}

apic_vmm_provider=VMware
apic_vmm_domain=openstack
apic_vlan_ns_name=openstack_ns
apic_node_profile=openstack_profile
apic_entity_profile=openstack_entity
apic_function_profile=openstack_function
apic_clear_node_profiles=True
apic_use_ssl=True

[apic_switch:101]
{HOSTNAME}={NEXUS_INTF_NUM}
'''


class ApicTest(BaseTestCase):

    APIC_HOST = os.environ.get('APIC_HOST')
    APIC_PORT = os.environ.get('APIC_PORT')
    APIC_USER = os.environ.get('APIC_USER')
    APIC_PASSWORD = os.environ.get('APIC_PASSWORD')

    @classmethod
    def create_ml2_conf_ini(cls):
        ini = ML2_APIC_INI.format(
            APIC_HOST=cls.APIC_HOST, APIC_PORT=cls.APIC_PORT,
            APIC_USER=cls.APIC_USER, APIC_PASSWORD=cls.APIC_PASSWORD,
            HOSTNAME=socket.gethostname(), NEXUS_INTF_NUM=NEXUS_INTF_NUM)
        path = os.path.join(WORKSPACE, APIC_CONF_FILES)
        with open(path, 'w') as f:
            f.write(ini)

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        clear_apic_config(cls.APIC_HOST, cls.APIC_PORT, cls.APIC_USER,
                          cls.APIC_PASSWORD, ssl=True)

        cls.create_ml2_conf_ini()
        cls.devstack.local_conf = LOCAL_CONF.format(
            neutron_repo=urlparse.urljoin(ZUUL_URL, ZUUL_PROJECT),
            neutron_branch=ZUUL_REF,
            Q_PLUGIN_EXTRA_CONF_PATH=WORKSPACE,
            Q_PLUGIN_EXTRA_CONF_FILES=APIC_CONF_FILES,
            vlan_start=NEXUS_VLAN_START, vlan_end=NEXUS_VLAN_END)
        # Next commit '1631af891af32eaa9af609398a88252ab437b0b4' forces
        # all openstack components to use keystone middleware but the APIC
        # does not support it
        cls.devstack.clone(commit='3163c17170b0b2bd7775e5e0d50040504b559ea1')

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(TEST_LIST_FILE))
