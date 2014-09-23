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

import logging
import subprocess
import os
import time
from ci import PARENT_FOLDER_PATH


logger = logging.getLogger(__name__)


def run_cmd_line(cmd_str, stderr=None, shell=False, check_result=True):
    logger.debug(cmd_str)
    cmd_args = cmd_str if shell else cmd_str.split()
    output = None
    return_code = 0
    try:
        output = subprocess.check_output(cmd_args, shell=shell, stderr=stderr)
    except subprocess.CalledProcessError as e:
        if check_result:
            logger.error(e)
            raise e
        else:
            return_code = e.returncode
    return output, return_code


def clear_nexus_config(ip, user, password, intf_num, vlan_start, vlan_end):
    logger.info('Clearing nexus config')
    script_path = os.path.join(PARENT_FOLDER_PATH,
                               'tools/clear_nexus_config.py')
    cmd = 'python {script} {ip} {user} {password} {intf_num} {vlan_start} ' \
          '{vlan_end}' \
          ''.format(script=script_path,
                    ip=ip, user=user, password=password,
                    intf_num=intf_num, vlan_start=vlan_start,
                    vlan_end=vlan_end)
    output, rc = run_cmd_line(cmd, check_result=False)


def get_public_key(host):
    cmd = 'ssh-keyscan -t rsa {host}'.format(host=host)
    output, code = run_cmd_line(cmd)
    return output


def wait_until(predicate, timeout=60, period=5):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if predicate():
                return True
        except Exception as e:
            logger.warning(e)
        time.sleep(period)
    return False


def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path)