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

import shutil
import os
from testtools import TestCase
from ci.lib.lab.node import Node
from ci.lib.utils import run_cmd_line, get_public_key, clear_nexus_config
from ci import jenkins_vars as var
from ci.lib.devstack import DevStack


class BaseTestCase(TestCase):

    NEUTRON_PROCESSES = [
        'neutron-server', 'neutron-openvswitch-agent',
        'neutron-dhcp-agent', 'neutron-l3-agent',
        'neutron-metadata-agent', 'neutron-lbaas-agent']

    @classmethod
    def setUpClass(cls):
        cls.devstack = DevStack()
        cls.node = Node()

        # Add fqdn to /etc/hosts
        run_cmd_line(
            'echo "{ip} {hostname}.slave.openstack.org {hostname}"'
            ' | sudo tee -a /etc/hosts'.format(ip=cls.node.ip,
                                               hostname=cls.node.hostname),
            shell=True)

        # Enable kernel networking functions
        run_cmd_line('echo "net.ipv4.ip_forward=1" '
                     '| sudo tee -a /etc/sysctl.conf', shell=True)
        run_cmd_line('echo "net.ipv4.conf.all.rp_filter=0" '
                     '| sudo tee -a /etc/sysctl.conf', shell=True)
        run_cmd_line('echo "net.ipv4.conf.default.rp_filter=0" '
                     '| sudo tee -a /etc/sysctl.conf', shell=True)
        run_cmd_line('sudo sysctl -p', shell=True)

        # Install custom ncclient
        ncclient_dir = '/opt/git/ncclient'
        if os.path.exists(ncclient_dir):
            run_cmd_line('sudo rm -rf {0}'.format(ncclient_dir), shell=True)
        run_cmd_line(
            'sudo pip uninstall -y ncclient', shell=True, check_result=False)
        run_cmd_line('sudo git clone --depth=1 -b master '
                     'https://github.com/CiscoSystems/ncclient.git '
                     '{NCCLIENT_DIR}'.format(NCCLIENT_DIR=ncclient_dir),
                     shell=True)
        try:
            os.chdir(ncclient_dir)
            run_cmd_line('sudo python setup.py install', shell=True)
        finally:
            os.chdir(var.WORKSPACE)

    @classmethod
    def tearDownClass(cls):
        # Copy local* files to workspace folder
        if cls.devstack.localrc is not None:
            shutil.copy(cls.devstack.localrc_path, var.WORKSPACE)
        if cls.devstack.local_conf is not None:
            shutil.copy(cls.devstack.localconf_path, var.WORKSPACE)

        # Copy screen logs to workspace
        run_cmd_line('find {p} -type l -exec cp "{{}}" {d} \;'
                     ''.format(p='/opt/stack/screen-logs', d=var.JOB_LOG_PATH),
                     shell=True)


class NexusTestCase(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        # Add nexus public key to known_hosts
        key = get_public_key(var.NEXUS_IP)
        with open(os.path.expanduser('~/.ssh/known_hosts'), 'w') as kh:
            kh.writelines(key)

        # Clear Nexus config
        clear_nexus_config(var.NEXUS_IP, var.NEXUS_USER,
                           var.NEXUS_PASSWORD, var.NEXUS_INTF_NUM,
                           var.NEXUS_VLAN_START, var.NEXUS_VLAN_END)

    @classmethod
    def tearDownClass(cls):
        BaseTestCase.tearDownClass()