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

import socket
import os
from ci import PARENT_FOLDER_PATH, \
    NEXUS_VLAN_START, NEXUS_VLAN_END, \
    NEXUS_INTF_NUM, NEXUS_IP, NEXUS_USER, NEXUS_PASSWORD
from ci.lib.test_case import BaseTestCase


TEST_LIST_FILE = os.path.join(PARENT_FOLDER_PATH, 'cisco_csr1kv_tests.txt')
LOCALRC = '''
# +------------------------------------------------------------------------------------------------+
# |                                                                                                |
# |  PLEASE NOTE: You MUST set those variables below that are marked with <SET THIS VARIABLE!!!>.  |
# |                                                                                                |
# +------------------------------------------------------------------------------------------------+

NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

DEBUG=True
VERBOSE=True

# ``HOST_IP`` should be set manually for best results if the NIC configuration
# of the host is unusual, i.e. ``eth1`` has the default route but ``eth0`` is the
# public interface.  It is auto-detected in ``stack.sh`` but often is indeterminate
# on later runs due to the IP moving from an Ethernet interface to a bridge on
# the host. Setting it here also makes it available for ``openrc`` to include
# when setting ``OS_AUTH_URL``.
# ``HOST_IP`` is not set by default.
#MULTI_HOST=True
HOST_IP=10.0.197.12
FIXED_RANGE=10.11.12.0/24
FIXED_NETWORK_SIZE=256
FLAT_INTERFACE=eth0
NETWORK_GATEWAY=10.11.12.1
FLOATING_RANGE=10.0.197.0/24
PUBLIC_NETWORK_GATEWAY=10.0.197.1
LIBVIRT_FIREWALL_DRIVER=nova.virt.firewall.NoopFirewallDriver

# Use br-int as bridge to reach external networks
PUBLIC_BRIDGE=br-int

our_pw=stack
# Must use hard coded value, as scripts grep for the following variables.
MYSQL_PASSWORD=$our_pw
RABBIT_PASSWORD=$our_pw
SERVICE_TOKEN=$our_pw
SERVICE_PASSWORD=$our_pw
ADMIN_PASSWORD=$our_pw

disable_service heat h-api h-api-cfn h-api-cw h-eng
disable_service n-net
enable_service neutron
enable_service q-svc
disable_service q-agt
disable_service q-l3
enable_service q-dhcp
enable_service ciscocfgagent
enable_service q-ciscorouter
#enable_service cisco_vpn
#enable_service q-fwaas
enable_service n-novnc

enable_plugin networking-cisco {net_cisco_repo} {net_cisco_ref}
enable_service net-cisco

# Destination path for installation of the OpenStack components.
# There is no need to specify it unless you want the code in
# some particular location (like in a directory shared by all VMs).
DEST=/opt/stack
SCREEN_LOGDIR=$DEST/logs
LOGFILE=~/devstack/stack.sh.log

# Settings to get NoVNC to work.
VNCSERVER_LISTEN=$HOST_IP
VNCSERVER_PROXYCLIENT_ADDRESS=$HOST_IP

# Type of virtualization to use. Options: kvm, lxc, qemu
LIBVIRT_TYPE=kvm
# Uncomment this to use LXC virtualization.
#LIBVIRT_TYPE=lxc

# List of images to use.
# ----------------------
case "$LIBVIRT_TYPE" in
    lxc) # the cirros root disk in the uec tarball is empty, so it will not work for lxc
        IMAGE_URLS="http://cloud-images.ubuntu.com/releases/oneiric/release/ubuntu-11.10-server-cloudimg-amd64.tar.gz,http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-rootfs.img.gz";;
    *)  # otherwise, use the uec style image (with kernel, ramdisk, disk)
        IMAGE_URLS="http://cloud-images.ubuntu.com/releases/oneiric/release/ubuntu-11.10-server-cloudimg-amd64.tar.gz,http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-uec.tar.gz";;
esac

Q_PLUGIN=cisco
declare -a Q_CISCO_PLUGIN_SUBPLUGINS=(n1kv)
Q_CISCO_PLUGIN_RESTART_VSM=yes
Q_CISCO_PLUGIN_VSM_IP=192.168.168.2
Q_CISCO_PLUGIN_VSM_USERNAME=admin
Q_CISCO_PLUGIN_VSM_PASSWORD=Sfish123
Q_CISCO_PLUGIN_VSM_ISO_IMAGE=/home/localadmin/csr1kv/images/n1kv/n1000v-dk9.5.2.1.SK3.1.0.181.iso
Q_CISCO_PLUGIN_UVEM_DEB_IMAGE=/home/localadmin/csr1kv/images/n1kv/nexus_1000v_vem-12.04-5.2.1.SK3.1.0.181.S0-0gdb.deb
#Q_CISCO_PLUGIN_HOST_MGMT_INTF=eth0
#Q_CISCO_PLUGIN_UPSTREAM_INTF=eth1
#Q_CISCO_PLUGIN_UPLINK2_INTF=eth1
NOVA_USE_QUANTUM_API=v2
N1KV_VLAN_NET_PROFILE_NAME=default_network_profile
N1KV_VLAN_NET_SEGMENT_RANGE=100-499

Q_CISCO_MGMT_CFG_AGENT_IP=10.0.200.2
Q_CISCO_MGMT_SUBNET=10.0.200.0
Q_CISCO_MGMT_SUBNET_USAGE_RANGE_START=10.0.200.10
Q_CISCO_MGMT_SUBNET_USAGE_RANGE_END=10.0.200.254

Q_CISCO_ROUTER_PLUGIN=yes
Q_CISCO_CSR1KV_QCOW2_IMAGE=/home/localadmin/csr1kv/images/csr1000v-universalk9.03.13.00.S.154-3.S-ext.qcow2

GIT_BASE=https://github.com

# Until ncclient pipy packages contains the latest change for CSR1kv we fetch the needed version like this.
NCCLIENT_VERSION=0.4.1
NCCLIENT_REPO=${GIT_BASE}/leopoul/ncclient.git
NCCLIENT_COMMIT_ID=bafd9b22e2fb423a577ed9c91d28272adbff30d3

# Global Openstack requirements
# Cisco doesn't currently have a requirements fork so use bob's fork
#REQUIREMENTS_REPO=${GIT_BASE}/bobmel/requirements.git
#REQUIREMENTS_REPO=${GIT_BASE}/CiscoSystems/requirements.git
#REQUIREMENTS_BRANCH=csr1kv_for_routing_juno

# Neutron service
#NEUTRON_REPO=${GIT_BASE}/cisco-openstack/neutron.git
#NEUTRON_BRANCH=staging/junoplus

# Neutron client
#NCCLIENT_VERSION=0.4.1
#NCCLIENT_REPO=${GIT_BASE}/leopoul/ncclient.git
#NCCLIENT_COMMIT_ID=bafd9b22e2fb423a577ed9c91d28272adbff30d3
#NEUTRONCLIENT_REPO=${GIT_BASE}/CiscoSystems/python-neutronclient.git
#NEUTRONCLIENT_BRANCH=

# Horizon
#HORIZON_REPO=${GIT_BASE}/CiscoSystems/horizon.git
#HORIZON_BRANCH=

VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
'''


class Csr1kvTest(BaseTestCase):

    neutron_repo = os.environ.get('NEUTRON_REPO')
    neutron_ref = os.environ.get('NEUTRON_REF')

    net_cisco_repo = os.environ.get('NET_CISCO_REPO')
    net_cisco_ref = os.environ.get('NET_CISCO_REF')

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        localrc = LOCALRC.format(
            neutron_repo=cls.neutron_repo,
            neutron_branch=cls.neutron_ref,
            net_cisco_repo=cls.net_cisco_repo,
            net_cisco_ref=cls.net_cisco_ref)

        cls.devstack.localrc = localrc
        cls.devstack._git_branch = 'csr1kv-ci'
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(TEST_LIST_FILE))

    def tearDown(self):
        self.devstack.unstack()
