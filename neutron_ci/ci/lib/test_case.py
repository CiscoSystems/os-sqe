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
import shutil
import os
import stat
import time
import StringIO
from testtools import TestCase
from netaddr import IPNetwork
from ci import WORKSPACE, SCREEN_LOG_PATH, NEXUS_IP, NEXUS_USER, \
    NEXUS_PASSWORD, NEXUS_INTF_NUM, NEXUS_VLAN_START, \
    NEXUS_VLAN_END, PARENT_FOLDER_PATH, OS_AUTH_URL, OS_USERNAME, OS_PASSWORD, OS_TENANT_NAME, OS_IMAGE_NAME
from ci.lib.lab.node import Node
from ci.lib.openstack import OpenStack
from ci.lib.utils import run_cmd_line, get_public_key, clear_nexus_config
from ci.lib.devstack import DevStack
from fabric.context_managers import settings, cd
from fabric.contrib.files import append, exists
from fabric.operations import put, run, local, sudo
from fabric.state import env


logger = logging.getLogger(__name__)


class BaseTestCase(TestCase):

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
        except Exception as e:
            logger.error(e)
        finally:
            os.chdir(WORKSPACE)

    @classmethod
    def tearDownClass(cls):
        # Copy local* files to workspace folder
        if cls.devstack.localrc is not None:
            shutil.copy(cls.devstack.localrc_path, WORKSPACE)
        if cls.devstack.local_conf is not None:
            shutil.copy(cls.devstack.localconf_path, WORKSPACE)

        # Copy screen logs to workspace
        run_cmd_line('find {p} -type l -exec cp "{{}}" {d} \;'
                     ''.format(p='/opt/stack/screen-logs', d=SCREEN_LOG_PATH),
                     shell=True)


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
        VirtualMachine = namedtuple('VirtualMachine', ['ip', 'mac', 'port', 'name'])
        # Fabric's environment variables
        env.disable_known_hosts = True
        env.abort_exception = Exception
        env.key_filename = os.path.expanduser('~/id_rsa')
        env.user = 'ubuntu'

        cls.admin_net = cls.get_free_subnet('192.168.0.0/16', 24)
        cls.disks = []

        # Parameters
        TITANIUM_IMG = os.environ.get(
            'TITANIUM_IMG',
            os.path.expanduser('~/titanium.qcow'))
        USER_DATA_YAML = os.environ.get(
            'USER_DATA_YAML',
            os.path.join(PARENT_FOLDER_PATH, 'files/2-role/user-data.yaml'))
        DNS = os.environ.get('DNS', '8.8.8.8')
        LIBVIRT_IMGS = '/var/lib/libvirt/images'
        UBUNTU_CLOUD_IMG = os.path.expanduser('~/devstack-trusty-1409997660.template.openstack.org.qcow')
        IMAGES_PATH = os.path.expanduser('~/images')
        DISK_SIZE = 20
        ID = int(time.time())

        # Download fresh ubuntu image
        # cls.openstack = OpenStack(OS_AUTH_URL, OS_USERNAME, OS_PASSWORD, OS_TENANT_NAME)
        # image = cls.openstack.find_image(OS_IMAGE_NAME)
        # if not os.path.exists(IMAGES_PATH):
        #     os.makedirs(IMAGES_PATH)
        # UBUNTU_CLOUD_IMG = os.path.join(IMAGES_PATH, image['name'] + '.qcow')
        # if not os.path.exists(UBUNTU_CLOUD_IMG):
        #     cls.openstack.download_image(image, UBUNTU_CLOUD_IMG)
        #
        # # Remove old images
        # files = (os.path.join(IMAGES_PATH, fn) for fn in os.listdir(IMAGES_PATH))
        # files = [(os.stat(path)[stat.ST_CTIME], path) for path in files]
        # for path in sorted(files, reverse=True)[2:]:
        #     os.remove(path[1])

        cls.VMs = {
            'control': VirtualMachine(ip=str(cls.admin_net[2]),
                                      mac=cls.rand_mac(),
                                      port='2/1',
                                      name='control-{0}'.format(ID),),
            'compute': VirtualMachine(ip=str(cls.admin_net[3]),
                                      mac=cls.rand_mac(),
                                      port='2/2',
                                      name='compute-{0}'.format(ID))}
        cls.TITANIUM = 'titanium-{0}'.format(ID)
        cls.BRIDGE1 = 'br{0}-1'.format(ID)
        cls.BRIDGE2 = 'br{0}-2'.format(ID)
        cls.ADMIN_NAME = 'admin-{0}'.format(ID)
        cls.MGMT_NAME = 'mgmt-{0}'.format(ID)

        ubuntu_img_path = os.path.join(LIBVIRT_IMGS, 'ubuntu-cloud{0}.qcow'.format(ID))
        local('sudo qemu-img convert -O qcow2 {source} {dest}'.format(
            source=UBUNTU_CLOUD_IMG, dest=ubuntu_img_path))
        cls.disks.append(ubuntu_img_path)

        # Create admin network
        with open(os.path.join(PARENT_FOLDER_PATH, 'files/2-role/admin-net.xml')) as f:
            tmpl = f.read().format(name=cls.ADMIN_NAME, ip=cls.admin_net[1],
                                   ip_start=cls.admin_net[2], ip_end=cls.admin_net[254],
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

        # Create management network
        with open(os.path.join(PARENT_FOLDER_PATH, 'files/2-role/mgmt-net.xml')) as f:
            tmpl = f.read().format(name=cls.MGMT_NAME)
            tmpl_path = '/tmp/mgmt-net{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh net-define {file}'.format(file=tmpl_path))
            local('sudo virsh net-autostart {0}'.format(cls.MGMT_NAME))
            local('sudo virsh net-start {0}'.format(cls.MGMT_NAME))

        # Create bridges
        for br in (cls.BRIDGE1, cls.BRIDGE2):
            local('sudo brctl addbr {0}'.format(br))
            local('sudo ip link set dev {0} up'.format(br))

        # Create control-server
        control_server_disk = os.path.join(LIBVIRT_IMGS, 'control{0}.qcow'.format(ID))
        control_conf_disk = os.path.join(LIBVIRT_IMGS, 'control-config{0}.qcow'.format(ID))
        local('sudo qemu-img create -f qcow2 -b {s} {d} {size}G'.format(
            s=ubuntu_img_path, d=control_server_disk, size=DISK_SIZE))
        local('sudo cloud-localds {d} {user_data}'.format(
            d=control_conf_disk, user_data=USER_DATA_YAML))
        cls.disks.append(control_server_disk)
        cls.disks.append(control_conf_disk)

        with open(os.path.join(PARENT_FOLDER_PATH, 'files/2-role/control-server.xml')) as f:
            tmpl = f.read().format(
                name=cls.VMs['control'].name,
                admin_net_name=cls.ADMIN_NAME,
                mgmt_net_name=cls.MGMT_NAME,
                disk=control_server_disk, disk_config=control_conf_disk,
                admin_mac=cls.VMs['control'].mac, bridge=cls.BRIDGE1)
            tmpl_path = '/tmp/control-server{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh define {s}'.format(s=tmpl_path))
            local('sudo virsh start {0}'.format(cls.VMs['control'].name))

        # Create compute-server
        compute_server_disk = os.path.join(LIBVIRT_IMGS, 'compute{0}.qcow'.format(ID))
        compute_conf_disk = os.path.join(LIBVIRT_IMGS, 'compute-config{0}.qcow'.format(ID))
        local('sudo qemu-img create -f qcow2 -b {s} {d} {size}G'.format(
            s=ubuntu_img_path, d=compute_server_disk, size=DISK_SIZE))
        local('sudo cloud-localds {d} {user_data}'.format(
            d=compute_conf_disk, user_data=USER_DATA_YAML))
        cls.disks.append(compute_server_disk)
        cls.disks.append(compute_conf_disk)

        with open(os.path.join(PARENT_FOLDER_PATH, 'files/2-role/compute-server.xml')) as f:
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
        titanium_disk = os.path.join(LIBVIRT_IMGS, 'titanium{0}.qcow'.format(ID))
        local('sudo cp {source} {dest}'.format(
            source=TITANIUM_IMG, dest=titanium_disk))
        cls.disks.append(titanium_disk)
        with open(os.path.join(PARENT_FOLDER_PATH, 'files/2-role/titanium.xml')) as f:
            tmpl = f.read().format(
                name=cls.TITANIUM,
                mgmt_net_name=cls.MGMT_NAME,
                disk=titanium_disk,
                bridge1=cls.BRIDGE1, bridge2=cls.BRIDGE2)
            tmpl_path = '/tmp/titanium{0}.xml'.format(ID)
            with open(tmpl_path, 'w') as o:
                o.write(tmpl)
            local('sudo virsh define {s}'.format(s=tmpl_path))
            local('sudo virsh start {0}'.format(cls.TITANIUM))

        # sleep while instances are booting
        time.sleep(30)

        resolv_conf = StringIO.StringIO()
        resolv_conf.write('nameserver {ip}\n'.format(ip=DNS))

        hosts_ptrn = '{ip} {hostname}.slave.openstack.org {hostname}\n'
        hosts = hosts_ptrn.format(ip=cls.VMs['control'].ip, hostname='control-server')
        hosts += hosts_ptrn.format(ip=cls.VMs['compute'].ip, hostname='compute-server')
        for vm in cls.VMs.itervalues():
            with settings(host_string=vm.ip):
                # hostname
                hostname = StringIO.StringIO()
                hostname.write(vm.name)
                put(hostname, '/etc/hostname', use_sudo=True)
                sudo('hostname {0}'.format(vm.name))

                # hosts
                append('/etc/hosts', hosts, use_sudo=True)

                # resolv.conf
                append('/etc/resolvconf/resolv.conf.d/head', resolv_conf, use_sudo=True)

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
                run('sudo ifup eth1')

                # Install custom (Cisco) ncclient
                ncclient_dir = '/opt/git/ncclient'
                if exists(ncclient_dir):
                    run('sudo rm -rf {0}'.format(ncclient_dir))
                run('sudo pip uninstall -y ncclient || :')
                run('sudo git clone --depth=1 -b master '
                    'https://github.com/CiscoSystems/ncclient.git '
                    '{NCCLIENT_DIR}'.format(NCCLIENT_DIR=ncclient_dir))
                with cd(ncclient_dir):
                    run('sudo python setup.py install')

                # Install pip packages
                run('sudo pip install junitxml')

        with settings(host_string=cls.VMs['control'].ip):
            # Configure eth2. Used to connect to Titanium mgmt interface
            eth2_cfg = StringIO.StringIO()
            eth2_cfg.writelines([
                'auto eth2\n',
                'iface eth2 inet static\n',
                '\taddress 192.168.254.2\n',
                '\tnetmask 255.255.255.0\n',
                '\tgateway 192.168.254.1'])
            put(eth2_cfg, '/etc/network/interfaces.d/eth2.cfg',
                use_sudo=True)
            run('sudo ifup eth2')
            run('sudo ip link set dev eth2 mtu 1450')

            # Wait for Titanium VM
            with settings(warn_only=True):
                nexus_ready = lambda: not run('ping -c 1 {ip}'.format(ip=NEXUS_IP)).failed
                for i in range(50):
                    if nexus_ready():
                       break
                    time.sleep(6)
                if not nexus_ready():
                    raise Exception('Titanium VM is not online')

            # Add titanium public key to known_hosts
            run('ssh-keyscan -t rsa {ip} >> '
                '~/.ssh/known_hosts'.format(ip=NEXUS_IP))

    @classmethod
    def tearDownClass(cls):
        with settings(warn_only=True):
            # Undefine virtual machines
            for key, vm in cls.VMs.iteritems():
                local('sudo virsh destroy {0}'.format(vm.name))
                local('sudo virsh undefine {0}'.format(vm.name))

            # Undefine titanium VM
            local('sudo virsh destroy {0}'.format(cls.TITANIUM))
            local('sudo virsh undefine {0}'.format(cls.TITANIUM))

            # Undefine networks
            for name in (cls.ADMIN_NAME, cls.MGMT_NAME):
                local('sudo virsh net-destroy {0}'.format(name))
                local('sudo virsh net-undefine {0}'.format(name))

            # Delete bridges
            for name in (cls.BRIDGE1, cls.BRIDGE2):
                local('sudo ip link set dev {0} down'.format(name))
                local('sudo brctl delbr {0}'.format(name))

            # Delete disks
            for d in cls.disks:
                local('sudo rm {0}'.format(d))
