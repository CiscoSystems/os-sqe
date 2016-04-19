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

import os
import time

import ci
from ci.lib import test_case
from ci.lib import utils

HW_FILE_PATH = os.path.join(ci.PARENT_FOLDER_PATH, 'files/ironic')
OPENRC_PATH = os.path.join(ci.WORKSPACE, 'devstack/openrc')

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
ENABLE_ISOLATED_METADATA=True

SWIFT_ENABLE_TEMPURLS=True

IRONIC_DEPLOY_DRIVER_ISCSI_WITH_IPA=True

IRONIC_ENABLED_DRIVERS=fake,pxe_iscsi_cimc,pxe_agent_cimc,pxe_ucs
IRONIC_DEPLOY_DRIVER={enabled_driver}

IRONIC_BUILD_DEPLOY_RAMDISK=False

IRONIC_BAREMETAL_BASIC_OPS=True

VIRT_DRIVER=ironic

IRONIC_IS_HARDWARE=True
IRONIC_HW_NODE_CPU=40
IRONIC_HW_NODE_RAM=131072
IRONIC_HW_NODE_DISK=500
IRONIC_HW_ARCH=x86_64
IRONIC_HWINFO_FILE={hw_file}

DEFAULT_INSTANCE_TYPE=baremetal
BUILD_TIMEOUT=2400
TEMPEST_SSH_CONNECT_METHOD=fixed

DOWNLOAD_DEFAULT_IMAGES=False
IMAGE_URLS="http://10.0.196.242/dashboard/static/ubuntu-dhcp.qcow2"
DEFAULT_IMAGE_NAME=ubuntu-dhcp
DEFAULT_INSTANCE_USER=ubuntu

VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True
PIP_UPGRADE=True

enable_plugin ironic {ironic_repo} {ironic_ref}

disable_service n-net n-novnc
enable_service q-svc q-agt q-dhcp q-meta
enable_service neutron

enable_service ironic ir-api ir-cond

enable_service s-proxy s-object s-container s-account

disable_service horizon

disable_service heat h-api h-api-cfn h-api-cw h-eng

disable_service cinder c-sch c-api c-vol

enable_service tempest

[[post-config|$NOVA_CONF]]
[DEFAULT]
quota_cores = -1
quota_ram = -1
[ironic]
api_max_retries = 120

[[post-extra|$TEMPEST_CONFIG]]
[DEFAULT]
debug = false
[baremetal]
power_timeout = 180
deploywait_timeout = 180
'''


class IronicTestCase(test_case.BaseTestCase):

    enabled_driver = "pxe_ipmitool"

    @classmethod
    def setUpClass(cls):
        super(IronicTestCase, cls).setUpClass()

        ironic_repo = os.environ.get('IRONIC_REPO')
        ironic_ref = os.environ.get('IRONIC_REF')
        hw_file_name = os.environ.get('IRONIC_HW_FILE')
        hw_file = os.path.join(HW_FILE_PATH, hw_file_name)
        cls.hw_info = open(hw_file, 'r').readline().split()

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
            hw_file=hw_file,
            enabled_driver=cls.enabled_driver)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def _fix_ironic_tempest_flavor(self):
        # Update tempest configuration to contain the uuid of the baremetal
        # flavor for the flavor_ref and flavor_ref_alt
        (flavor_id, code) = utils.run_cmd_line(
            'bash -c "source %s admin admin > /dev/null && '
            'openstack flavor show '
            'baremetal -f value -c id"' % OPENRC_PATH,
            shell=True,
            check_result=False)

        self.assertEqual(
            code, 0, message="Baremetal flavor doesn't exist: %s" % flavor_id)

        (result, code) = utils.run_cmd_line(
            'bash -c "source %s admin admin > /dev/null && '
            'iniset /opt/stack/tempest/etc/tempest.conf '
            'compute flavor_ref %s"' % (OPENRC_PATH, flavor_id),
            shell=True,
            check_result=False)

        self.assertEqual(
            code, 0, message="Failed to configure flavor_ref: %s" % result)

        (result, code) = utils.run_cmd_line(
            'bash -c "source %s admin admin > /dev/null && '
            'iniset /opt/stack/tempest/etc/tempest.conf '
            'compute flavor_ref_alt %s"' % (OPENRC_PATH, flavor_id),
            shell=True,
            check_result=False)

        self.assertEqual(
            code, 0, message="Failed to configure flavor_ref_alt: %s" % result)

    def start_devstack(self):
        self.assertFalse(self.devstack.stack())
        self._fix_ironic_tempest_flavor()

    def run_cmd_with_openrc(self, cmd):
        activate_openrc = (
            'bash -c "source %s admin admin > /dev/null && ' % OPENRC_PATH)
        return utils.run_cmd_line(
            "%s%s" % (activate_openrc, cmd), shell=True, check_result=False)

    def run_ironic_tempest(self):
        # Sleep for 2 minutes after updating Ironic to make sure nova picks up
        # the ironic changes.
        time.sleep(120)

        self.assertFalse(self.devstack.run_tempest(
            '--concurrency=1',
            'ironic',
            all_plugin=True,
            env_args={
                'OS_TEST_TIMEOUT': 3000
            }
        ))
