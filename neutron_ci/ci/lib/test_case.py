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
from collections import namedtuple

import logging
import random
import os
import time
import StringIO
from testtools import TestCase
from netaddr import IPNetwork
from ci import WORKSPACE, BUILD_LOG_PATH, NEXUS_IP, NEXUS_USER, \
    NEXUS_PASSWORD, NEXUS_INTF_NUM, NEXUS_VLAN_START, \
    NEXUS_VLAN_END, PARENT_FOLDER_PATH, NODE_DEFAULT_ETH, \
    OFFLINE_NODE_WHEN_COMPLETE
from ci.lib.lab.node import Node
from ci.lib.utils import run_cmd_line, get_public_key, \
    clear_nexus_config, wait_until
from ci.lib.devstack import DevStack
from fabric.context_managers import settings
from fabric.contrib.files import append
from fabric.operations import put, run, local, sudo
from fabric.state import env


logger = logging.getLogger(__name__)


class BaseTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.devstack = DevStack(clone_path=os.path.join(WORKSPACE, 'devstack'))

        if OFFLINE_NODE_WHEN_COMPLETE:
            cls.node = Node(NODE_DEFAULT_ETH)

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
                run_cmd_line('sudo rm -rf {0}'.format(ncclient_dir),
                             shell=True)
            run_cmd_line(
                'sudo pip uninstall -y ncclient', shell=True,
                check_result=False)
            run_cmd_line('sudo git clone --depth=1 -b master '
                         'https://github.com/CiscoSystems/ncclient.git '
                         '{NCCLIENT_DIR}'.format(NCCLIENT_DIR=ncclient_dir),
                         shell=True)
            try:
                os.chdir(ncclient_dir)
                run_cmd_line('sudo python setup.py install', shell=True)
            except Exception as e:
                logger.error(e)
            finally:
                os.chdir(WORKSPACE)

    def setUp(self):
        super(BaseTestCase, self).setUp()
        if not OFFLINE_NODE_WHEN_COMPLETE:
            self.devstack.unstack()
            self.devstack.kill_python_apps()
            self.devstack.clear()
            self.devstack.clone_repositories(self.devstack._cloned_repos_path)
            self.devstack.rsync_repositories(self.devstack._cloned_repos_path)
            self.devstack.restart_ovs()

    @classmethod
    def tearDownClass(cls):
        # Copy local* files to workspace folder
        cls.devstack.get_locals(BUILD_LOG_PATH)
        cls.devstack.get_screen_logs(BUILD_LOG_PATH)

        p = os.path.join(BUILD_LOG_PATH, 'logs')
        cls.devstack.get_tempest_unitxml(p)
        cls.devstack.get_tempest_html(p)


class NexusTestCase(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        BaseTestCase.setUpClass()

        # Add nexus public key to known_hosts
        key = get_public_key(NEXUS_IP)
        with open(os.path.expanduser('~/.ssh/known_hosts'), 'w') as kh:
            kh.writelines(key)

        # Clear Nexus config
        clear_nexus_config(NEXUS_IP, NEXUS_USER,
                           NEXUS_PASSWORD, NEXUS_INTF_NUM,
                           NEXUS_VLAN_START, NEXUS_VLAN_END)

    @classmethod
    def tearDownClass(cls):
        BaseTestCase.tearDownClass()


class MultinodeTestCase(TestCase):

    @staticmethod
    def get_free_subnet(net_ip, subnet_cidr):
        net = IPNetwork(net_ip)
        with settings(warn_only=True):
            for n in net.subnet(subnet_cidr):
                if local('ping -c 1 {0}'.format(n[1])).failed:
                    return n

    @staticmethod
    def rand_mac():
        mac = [0x52, 0x54, 0x00,
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(["%02x" % x for x in mac])

    @classmethod
    def setUpClass(cls):
        # Fabric's environment variables
        env.disable_known_hosts = True
        env.abort_exception = Exception
        env.key_filename = os.path.join(WORKSPACE, 'id_rsa')
        env.user = 'ubuntu'

        # Parameters
        ID = int(time.time())
        USER_DATA_YAML = 'files/2-role/user-data.yaml'
        LIBVIRT_IMGS = '/var/lib/libvirt/images'
        UBUNTU_CLOUD_IMG = os.path.join(
            WORKSPACE, 'devstack-trusty.template.openstack.org.qcow')
        TITANIUM_IMG = os.path.join(WORKSPACE, 'titanium.qcow')
        DISK_SIZE = 20
        ADMIN_NET = cls.get_free_subnet('192.168.0.0/16', 24)
        MGMT_NET = IPNetwork('192.168.254.0/24')
        cls.TITANIUM = 'titanium-{0}'.format(ID)
        cls.BRIDGE_MGMT = 'br{0}-m'.format(ID)
        cls.BRIDGE1 = 'br{0}-1'.format(ID)
        cls.BRIDGE2 = 'br{0}-2'.format(ID)
        cls.ADMIN_NAME = 'admin-{0}'.format(ID)
        cls.MGMT_NAME = 'mgmt-{0}'.format(ID)

        VirtualMachine = namedtuple('VirtualMachine',
                                    ['ip', 'mac', 'port', 'name'])
        cls.VMs = {
            'control': VirtualMachine(ip=str(ADMIN_NET[2]),
                                      mac=cls.rand_mac(),
                                      port='2/1',
                                      name='control-{0}'.format(ID),),
            'compute': VirtualMachine(ip=str(ADMIN_NET[3]),
                                      mac=cls.rand_mac(),
                                      port='2/2',
                                      name='compute-{0}'.format(ID))}

        ubuntu_img_path = os.path.join(LIBVIRT_IMGS,
                                       'ubuntu-cloud{0}.qcow'.format(ID))
        local('sudo qemu-img convert -O qcow2 {source} {dest}'.format(
            source=UBUNTU_CLOUD_IMG, dest=ubuntu_img_path))

        # Create admin network
        admin_net_xml = os.path.join(PARENT_FOLDER_PATH,
                                     'files/2-role/admin-net.xml')
        with open(admin_net_xml) as f:
            tmpl = f.read().format(
                name=cls.ADMIN_NAME, ip=ADMIN_NET[1],
                ip_start=ADMIN_NET[2], ip_end=ADMIN_NET[254],
                control_servers_mac=cls.VMs['control'].mac,
                control_servers_ip=cls.VMs['control'].ip,
                compute_servers_mac=cls.VMs['compute'].mac,
                compute_servers_ip=cls.VMs['compute'].ip)
            tmpl_path = '/tmp/admin-net{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh net-define {file}'.format(file=tmpl_path))
            local('sudo virsh net-autostart {0}'.format(cls.ADMIN_NAME))
            local('sudo virsh net-start {0}'.format(cls.ADMIN_NAME))

        # Create bridges
        for br in (cls.BRIDGE1, cls.BRIDGE2, cls.BRIDGE_MGMT):
            local('sudo brctl addbr {0}'.format(br))
            local('sudo ip link set dev {0} up'.format(br))

        # Create control-server
        control_server_disk = os.path.join(LIBVIRT_IMGS,
                                           'control{0}.qcow'.format(ID))
        control_conf_disk = os.path.join(LIBVIRT_IMGS,
                                         'control-config{0}.qcow'.format(ID))
        local('sudo qemu-img create -f qcow2 -b {s} {d} {size}G'.format(
            s=ubuntu_img_path, d=control_server_disk, size=DISK_SIZE))
        local('sudo cloud-localds {d} {user_data}'.format(
            d=control_conf_disk, user_data=USER_DATA_YAML))

        cntrl_server_xml = os.path.join(PARENT_FOLDER_PATH,
                                        'files/2-role/control-server.xml')
        with open(cntrl_server_xml) as f:
            tmpl = f.read().format(
                name=cls.VMs['control'].name,
                admin_net_name=cls.ADMIN_NAME,
                bridge_mgmt=cls.BRIDGE_MGMT,
                disk=control_server_disk, disk_config=control_conf_disk,
                admin_mac=cls.VMs['control'].mac, bridge=cls.BRIDGE1)
            tmpl_path = '/tmp/control-server{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh define {s}'.format(s=tmpl_path))
            local('sudo virsh start {0}'.format(cls.VMs['control'].name))

        # Create compute-server
        compute_server_disk = os.path.join(LIBVIRT_IMGS,
                                           'compute{0}.qcow'.format(ID))
        compute_conf_disk = os.path.join(LIBVIRT_IMGS,
                                         'compute-config{0}.qcow'.format(ID))
        local('sudo qemu-img create -f qcow2 -b {s} {d} {size}G'.format(
            s=ubuntu_img_path, d=compute_server_disk, size=DISK_SIZE))
        local('sudo cloud-localds {d} {user_data}'.format(
            d=compute_conf_disk, user_data=USER_DATA_YAML))

        compute_server_xml = os.path.join(PARENT_FOLDER_PATH,
                                          'files/2-role/compute-server.xml')
        with open(compute_server_xml) as f:
            tmpl = f.read().format(
                name=cls.VMs['compute'].name,
                admin_net_name=cls.ADMIN_NAME,
                disk=compute_server_disk, disk_config=compute_conf_disk,
                admin_mac=cls.VMs['compute'].mac, bridge=cls.BRIDGE2)
            tmpl_path = '/tmp/compute-server{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh define {s}'.format(s=tmpl_path))
            local('sudo virsh start {0}'.format(cls.VMs['compute'].name))

        # Create Titanium VM
        titanium_disk = os.path.join(LIBVIRT_IMGS,
                                     'titanium{0}.qcow'.format(ID))
        local('sudo cp {source} {dest}'.format(
            source=TITANIUM_IMG, dest=titanium_disk))
        titanium_xml = os.path.join(PARENT_FOLDER_PATH,
                                    'files/2-role/titanium.xml')
        with open(titanium_xml) as f:
            tmpl = f.read().format(
                name=cls.TITANIUM,
                bridge_mgmt=cls.BRIDGE_MGMT,
                disk=titanium_disk,
                bridge1=cls.BRIDGE1, bridge2=cls.BRIDGE2)
            tmpl_path = '/tmp/titanium{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh define {s}'.format(s=tmpl_path))
            local('sudo virsh start {0}'.format(cls.TITANIUM))

        hosts_ptrn = '{ip} {hostname}.slave.openstack.org {hostname}\n'
        hosts = hosts_ptrn.format(ip=cls.VMs['control'].ip,
                                  hostname='control-server')
        hosts += hosts_ptrn.format(ip=cls.VMs['compute'].ip,
                                   hostname='compute-server')
        for vm in cls.VMs.itervalues():
            with settings(host_string=vm.ip):
                with settings(warn_only=True):
                    vm_ready = lambda: not run('ls').failed
                    if not wait_until(vm_ready, timeout=60 * 5):
                        raise Exception('VM {0} failed'.format(vm.name))

                # hostname
                hostname = StringIO.StringIO()
                hostname.write(vm.name)
                put(hostname, '/etc/hostname', use_sudo=True)
                sudo('hostname {0}'.format(vm.name))

                # hosts
                append('/etc/hosts', hosts, use_sudo=True)

                # configure eth1. Used for tenant networks. Bridged to
                # certain titanium interface
                eth1_cfg = StringIO.StringIO()
                eth1_cfg.writelines([
                    'auto eth1\n',
                    'iface eth1 inet manual\n',
                    '\tup ifconfig $IFACE 0.0.0.0 up\n',
                    '\tup ip link set $IFACE promisc on\n',
                    '\tdown ifconfig $IFACE 0.0.0.0 down'])
                put(eth1_cfg, '/etc/network/interfaces.d/eth1.cfg',
                    use_sudo=True)
                sudo('ifup eth1')

                sudo('ip link set dev eth0 mtu 1450')

        with settings(host_string=cls.VMs['control'].ip):
            # Configure eth2. Used to connect to Titanium mgmt interface
            eth2_cfg = StringIO.StringIO()
            eth2_cfg.writelines([
                'auto eth2\n',
                'iface eth2 inet static\n',
                '\taddress {0}\n'.format(MGMT_NET[2]),
                '\tnetmask {0}\n'.format(MGMT_NET.netmask),
                '\tgateway {0}'.format(MGMT_NET[1])])
            put(eth2_cfg, '/etc/network/interfaces.d/eth2.cfg',
                use_sudo=True)
            sudo('ifup eth2')

            # Wait for Titanium VM
            with settings(warn_only=True):
                nexus_ready = lambda: \
                    not run('ping -c 1 {ip}'.format(ip=NEXUS_IP)).failed
                if not wait_until(nexus_ready, timeout=60 * 5):
                    raise Exception('Titanium VM is not online')

            # Add titanium public key to known_hosts
            run('ssh-keyscan -t rsa {ip} >> '
                '~/.ssh/known_hosts'.format(ip=NEXUS_IP))
