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
from fabric.state import env

import os
import logging
import logging.handlers

# Jenkins variables
WORKSPACE = os.environ.get('WORKSPACE')
BUILD_LOG_PATH = os.path.join(WORKSPACE, 'logs')
PARENT_FOLDER_PATH = os.path.dirname(os.path.dirname(__file__))

# Zuul variables
BASE_LOG_PATH = os.environ.get('BASE_LOG_PATH')
ZUUL_PIPELINE = os.environ.get('ZUUL_PIPELINE')
OFFLINE_NODE_WHEN_COMPLETE = \
    os.environ.get('OFFLINE_NODE_WHEN_COMPLETE') == '1'
ZUUL_UUID = os.environ.get('ZUUL_UUID')
LOG_PATH = os.environ.get('LOG_PATH')
ZUUL_CHANGE_IDS = os.environ.get('ZUUL_CHANGE_IDS')
ZUUL_PATCHSET = os.environ.get('ZUUL_PATCHSET')
ZUUL_BRANCH = os.environ.get('ZUUL_BRANCH')
ZUUL_REF = os.environ.get('ZUUL_REF')
ZUUL_COMMIT = os.environ.get('ZUUL_COMMIT')
ZUUL_URL = os.environ.get('ZUUL_URL')
ZUUL_CHANGE = os.environ.get('ZUUL_CHANGE')
ZUUL_CHANGES = os.environ.get('ZUUL_CHANGES')
ZUUL_PROJECT = os.environ.get('ZUUL_PROJECT')

# Configurations
NEXUS_IP = os.environ.get('NEXUS_IP')
NEXUS_USER = os.environ.get('NEXUS_USER')
NEXUS_PASSWORD = os.environ.get('NEXUS_PASSWORD')
NEXUS_INTF_NUM = os.environ.get('NEXUS_INTF_NUM')
NEXUS_VLAN_START = os.environ.get('NEXUS_VLAN_START')
NEXUS_VLAN_END = os.environ.get('NEXUS_VLAN_END')

OS_AUTH_URL = os.environ.get('OS_AUTH_URL')
OS_USERNAME = os.environ.get('OS_USERNAME')
OS_PASSWORD = os.environ.get('OS_PASSWORD')
OS_TENANT_NAME = os.environ.get('OS_TENANT_NAME')

NODE_DEFAULT_ETH = os.environ.get('NODE_DEFAULT_ETH', 'eth0')

OS_IMAGE_NAME = \
    os.environ.get('OS_IMAGE_NAME',
                   'devstack-trusty-\d+.template.openstack.org')
OS_FLAVOR_NAME = os.environ.get('OS_FLAVOR_NAME', 'devstack.medium')
OS_DNS = os.environ.get('OS_DNS')

# Create log path
if not os.path.exists(BUILD_LOG_PATH):
    os.mkdir(BUILD_LOG_PATH)

# Configure handlers for the root logger
logger = logging.getLogger('ci')
formatter = logging.Formatter('%(asctime)s %(name)s: %(lineno)d, '
                              '%(levelname)s: %(message)s')

# Add console log handler
CONSOLE_LOG_LEVEL = int(os.environ.get('CONSOLE_LOG_LEVEL', logging.INFO))
console_handler = logging.StreamHandler()
console_handler.setLevel(CONSOLE_LOG_LEVEL)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
