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

import os
import logging

logger = logging.getLogger(__name__)

# Jenkins variables
WORKSPACE = os.environ.get('WORKSPACE')

# Zuul variables
BASE_LOG_PATH = os.environ.get('BASE_LOG_PATH')
ZUUL_PIPELINE = os.environ.get('ZUUL_PIPELINE')
OFFLINE_NODE_WHEN_COMPLETE = os.environ.get('OFFLINE_NODE_WHEN_COMPLETE')
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

JOB_LOG_PATH = os.path.join(WORKSPACE, 'logs')

# Configurations
NEXUS_IP = os.environ.get('NEXUS_IP')
NEXUS_USER = os.environ.get('NEXUS_USER')
NEXUS_PASSWORD = os.environ.get('NEXUS_PASSWORD')
NEXUS_INTF_NUM = os.environ.get('NEXUS_INTF_NUM')
NEXUS_VLAN_START = os.environ.get('NEXUS_VLAN_START')
NEXUS_VLAN_END = os.environ.get('NEXUS_VLAN_END')

# Print variables to debug log to help reproduce a build
values = locals()
msg = ['export {0}={1}'.format(key, values[key])
       for key in dir() if key[0].isupper()]
msg.insert(0, os.linesep)
logger.debug(os.linesep.join(msg))

# Raise exception if there are undefined variables
defined = [values[key] is not None for key in dir()
           if key[0].isupper()]
if not all(defined):
    raise Exception('There are undefined environment variables.')

if not os.path.exists(JOB_LOG_PATH):
    os.mkdir(JOB_LOG_PATH)
