# Copyright 2016 Cisco Systems, Inc.
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

from __future__ import print_function

import socket
import os
import ci
from ci.lib import test_case
from ci.lib import utils

HW_FILE_PATH = os.path.join(ci.PARENT_FOLDER_PATH, 'files/ironic')

LOCAL_CONF = '''
[[local|localrc]]
HOST_IP={host_ip}
ADMIN_PASSWORD=password
MYSQL_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SWIFT_HASH=$ADMIN_PASSWORD
SWIFT_TEMPURL_KEY=$ADMIN_PASSWORD

PUBLIC_INTERFACE={ironic_interface}
Q_L3_ENABLED=False
Q_USE_PROVIDER_NETWORKING=True
OVS_PHYSICAL_BRIDGE=br-{ironic_interface}
PHYSICAL_NETWORK=private
PROVIDER_NETWORK_TYPE="flat"
FIXED_RANGE="10.0.199.0/24"
NETWORK_GATEWAY="10.0.199.1"
ALLOCATION_POOL=start={allocation_start},end={allocation_end}

enable_plugin ironic git://git.openstack.org/openstack/ironic

disable_service n-net n-novnc
enable_service q-svc q-agt q-dhcp q-meta
enable_service neutron
enable_service tempest

enable_service s-proxy s-object s-container s-account

disable_service horizon

disable_service heat h-api h-api-cfn h-api-cw h-eng

disable_service cinder c-sch c-api c-vol

SWIFT_ENABLE_TEMPURLS=True

IRONIC_DEPLOY_DRIVER_ISCSI_WITH_IPA=True

IRONIC_ENABLED_DRIVERS=pxe_ipmitool,pxe_iscsi_cimc,pxe_agent_cimc
IRONIC_DEPLOY_DRIVER=pxe_ipmitool

IRONIC_BUILD_DEPLOY_RAMDISK=False

IRONIC_BAREMETAL_BASIC_OPS=True

VIRT_DRIVER=ironic

IRONIC_IS_HARDWARE=True
IRONIC_HW_NODE_CPU=40
IRONIC_HW_NODE_RAM=131072
IRONIC_HW_ARCH=x86_64
IRONIC_IPMIINFO_FILE={hw_file}

VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True
PIP_UPGRADE=True

[[post-config|$NOVA_CONF]]
[DEFAULT]
quota_cores = -1
quota_ram = -1
'''


class IronicCIMCDriverTestCase(test_case.BaseTestCase):

    @classmethod
    def setUpClass(cls):
        super(IronicCIMCDriverTestCase, cls).setUpClass()

        ironic_repo = os.environ.get('IRONIC_REPO')
        ironic_ref = os.environ.get('IRONIC_REF')
        hw_file_name = os.environ.get('IRONIC_HW_FILE')
        hw_file = os.path.join(HW_FILE_PATH, hw_file_name)

        (devices, code) = utils.run_cmd_line('ifconfig | grep Ethernet | '
                                             'cut -d" " -f 1', shell=True)
        devices = devices.splitlines()
        for dev in devices:
            (ip, code) = utils.run_cmd_line('ifconfig %s | '
                                            'grep "inet\ addr" | '
                                            'cut -d: -f2 | '
                                            'cut -d" " -f1' % dev, shell=True)
            ip = ip.strip()
            if '10.0.199' in ip:
                host = ip
                interface = dev

        start = os.environ.get('IRONIC_AL_START')
        end = os.environ.get('IRONIC_AL_END')

        local_conf = LOCAL_CONF.format(
            host_ip=host,
            ironic_interface=interface,
            ironic_repo=ironic_repo,
            ironic_ref=ironic_ref,
            allocation_start=start,
            allocation_end=end,
            hw_file=hw_file)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest('ironic', all_plugin=True))
