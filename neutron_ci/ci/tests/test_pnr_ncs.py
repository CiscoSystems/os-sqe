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
# @author: Yaroslav Morkovnikov, Cisco Systems, Inc.

from fabric.operations import local
import os
from ci import PARENT_FOLDER_PATH, WORKSPACE
from ci.lib.test_case import BaseTestCase

Q_PLUGIN_EXTRA_CONF_PATH = \
    '/opt/stack/networking-cisco/etc/neutron/plugins/ml2'
Q_PLUGIN_EXTRA_CONF_FILES = 'ml2_conf_ncs.ini'
LOCAL_CONF = '''
[[local|localrc]]
NEUTRON_REPO={neutron_repo}
NEUTRON_BRANCH={neutron_branch}

ADMIN_PASSWORD=secrete
MYSQL_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=secrete
RECLONE=no

HOST_IP=$(ip addr | grep inet | grep eth0 | awk -F" " '{{print $2}}'| sed -e 's/\/.*$//')

# misc
API_RATE_LIMIT=False

# log
DEBUG=True
VERBOSE=True
DEST=/opt/stack
LOGFILE=$DEST/logs/stack.sh.log
SCREEN_LOGDIR=$DEST/logs/screen

SYSLOG=False
LOG_COLOR=False
LOGDAYS=7

# enable pre-requisite
enable_service rabbit
enable_service mysql
enable_service key

enable_plugin networking-cisco https://git.openstack.org/openstack/networking-cisco.git
enable_service net-cisco

# keystone
KEYSTONE_CATALOG_BACKEND=sql

VOLUME_GROUP="stack-volumes"
VOLUME_NAME_PREFIX="volume-"
VOLUME_BACKING_FILE_SIZE=10250M

# enable neutron
disable_service n-net
enable_service q-svc
enable_service q-agt
enable_service q-dhcp
enable_service q-l3
enable_service q-meta
enable_service q-fwaas
enable_service q-lbaas
#enable_service q-vpn
enable_service neutron

# VLAN configuration
Q_PLUGIN=ml2
ENABLE_TENANT_VLANS=True

# GRE tunnel configuration
Q_PLUGIN=ml2
ENABLE_TENANT_TUNNELS=True

# VXLAN tunnel configuration
Q_PLUGIN=ml2
Q_ML2_TENANT_NETWORK_TYPE=vxlan


# enable horizon
enable_service horizon

# enable tempest
enable_service tempest

[[post-config|{Q_PLUGIN_EXTRA_CONF_PATH}/{Q_PLUGIN_EXTRA_CONF_FILES}]]
[ml2_ncs]
url=http://127.0.0.1:8888/openstack/
username=admin
password=admin
'''


class PNRFNCSTest(BaseTestCase):

    neutron_repo = os.environ.get('NEUTRON_REPO')
    neutron_ref = os.environ.get('NEUTRON_REF')

    net_cisco_repo = os.environ.get('NET_CISCO_REPO')
    net_cisco_ref = os.environ.get('NET_CISCO_REF')

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        local_conf = LOCAL_CONF.format(
            neutron_repo=cls.neutron_repo,
            neutron_branch=cls.neutron_ref,
            net_cisco_repo=cls.net_cisco_repo,
            net_cisco_ref=cls.net_cisco_ref,
            Q_PLUGIN_EXTRA_CONF_PATH=WORKSPACE,
            Q_PLUGIN_EXTRA_CONF_FILES=Q_PLUGIN_EXTRA_CONF_FILES)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(
            'tempest.api.network.test_networks '
            'tempest.api.network.test_ports '))
