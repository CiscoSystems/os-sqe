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
from ci import PARENT_FOLDER_PATH
from ci.lib.test_case import BaseTestCase

from fabric.operations import local
from ci.lib.devstack import DevStack

from ci import BUILD_LOG_PATH

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
Q_ML2_PLUGIN_MECHANISM_DRIVERS=openvswitch,cisco_ucsm
Q_ML2_PLUGIN_TYPE_DRIVERS=vlan
ENABLE_TENANT_TUNNELS=False
Q_ML2_TENANT_NETWORK_TYPE=local
Q_PLUGIN_EXTRA_CONF_PATH=({Q_PLUGIN_EXTRA_CONF_PATH})
Q_PLUGIN_EXTRA_CONF_FILES=({Q_PLUGIN_EXTRA_CONF_FILES})
ML2_VLAN_RANGES=physnet1:100:200
PHYSICAL_NETWORK=physnet1
OVS_PHYSICAL_BRIDGE=br-eth1
TENANT_VLAN_RANGE=100:200
ENABLE_TENANT_VLANS=True
IP_VERSION=4
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/opt/stack/screen-logs/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/screen-logs
RECLONE=True
PIP_UPGRADE=True
API_WORKERS=0

[[post-config|{Q_PLUGIN_EXTRA_CONF_PATH}/{Q_PLUGIN_EXTRA_CONF_FILES}]]
[ml2_cisco_ucsm]
ucsm_ip=172.21.19.10
ucsm_username=admin
ucsm_password=Cisc0123
ucsm_host_list=neutron1:neutron1
'''


class ML2UCSMTest(BaseTestCase):

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
            Q_PLUGIN_EXTRA_CONF_PATH=Q_PLUGIN_EXTRA_CONF_PATH,
            Q_PLUGIN_EXTRA_CONF_FILES=Q_PLUGIN_EXTRA_CONF_FILES)

        cls.devstack.local_conf = local_conf
        cls.devstack.clone()

        # Delete user sessions
        script = 'python ' + os.path.join(
            PARENT_FOLDER_PATH,
            'files/ucsm/ucsm_delete_admin_sessions.py')
        local(script)

        # Clear VLANs and port profiles
        script = 'python ' + os.path.join(
            PARENT_FOLDER_PATH,
            'files/ucsm/ucsm_clear.py')
        local(script + ' --ip 172.21.19.10 --username admin --password Cisc0123 --skip-vlans 1,519')

        cls.hm_devstack = DevStack()
        cls.hm_devstack._tempest_path = os.path.join(cls.devstack._tempest_path, '../hm_tempest') 

    def test_tempest(self):
        self.assertFalse(self.devstack.stack())
        self.assertFalse(self.devstack.run_tempest(
            test_list_path=TEST_LIST_FILE))

        # Run home-made UCSM tests
        params = self.devstack.get_ini(
            self.devstack.tempest_conf,
            {'auth': ['admin_password', 'admin_username', 'admin_tenant_id',
                      'admin_tenant_name', 'admin_domain_name'],
             'compute': ['ssh_user']})
        new_params = {'compute': {'image_ssh_user': params['compute']['ssh_user']},
                      'identity': params['auth'],
                      'ucsm': {'ucsm_ip': '172.21.19.10',
                               'ucsm_username': 'admin',
                               'ucsm_password': 'Cisc0123',
                               'compute_host_dict': 'neutron1:org-root/ls-neutron1',
                               'controller_host_dict': 'neutron1:org-root/ls-neutron1',
                               'eth_names': 'eth0',
                               'test_connectivity': 'False'}}

        self.hm_devstack.get_tempest(
            self.hm_devstack._tempest_path,
            'https://github.com/cisco-openstack/tempest.git', 'proposed',
            self.devstack.tempest_conf, tempest_config_params=new_params)
        self.assertFalse(self.hm_devstack.run_tempest('tempest.thirdparty.cisco'))

    @classmethod
    def tearDownClass(cls):
        BaseTestCase.tearDownClass()
        p = os.path.join(BUILD_LOG_PATH, 'logs')
        cls.hm_devstack.get_tempest_html(p, 'cisco_ucsm_results.html')

