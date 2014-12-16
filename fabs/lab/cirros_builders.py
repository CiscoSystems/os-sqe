# Copyright 2014 Cisco Systems, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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

from fabric.api import local, lcd
from fabs import lab


def build_new():
    """Build new cirros image in buildroot way"""
    local_tar = lab.wget_file(local_dir=lab.CIRROS_BLD_DIR, file_url=lab.CIRROS_BUILD_ROOT_URL)
    with lcd(lab.CIRROS_BLD_DIR):
        local('tar xf ' + local_tar)
    bld_dir = local_tar.split('.tar.gz')[0]
    local('cp {0} {1}/.config'.format(lab.CIRROS_CONFIG, bld_dir))
    with lcd(bld_dir):
        local('make')


def build_old():
    """Build new cirros image"""

    local('mkdir -p {0}'.format(lab.CIRROS_BLD_DIR))
    with lcd(lab.CIRROS_BLD_DIR):
        local('rm -rf cirros && bzr branch lp:cirros')
        build_root_local = lab.wget_file(local_dir='.', file_url=lab.CIRROS_BUILD_ROOT_URL)
        kernel_local = lab.wget_file(local_dir='.', file_url=lab.CIRROS_KERNEL_URL)
        local('rm -rf {0} && tar -xf {1}'.format(build_root_local.strip('.tar.gz'), build_root_local))
    with lcd(lab.CIRROS_BLD_DIR + '/cirros'):
        local('ln -nsf ../{0} buildroot'.format(build_root_local.strip('.tar.gz')))
        local('ln -sf ../{0} {0}'.format(kernel_local))
    with lcd(lab.CIRROS_BLD_DIR + '/cirros/buildroot'):
        local('QUILT_PATCHES={0}/patches-buildroot quilt push -a'.format(lab.CIRROS_BLD_DIR+'/cirros'))

    with lcd(lab.CIRROS_BLD_DIR + '/cirros'):
        local('patch -p0 < {0} && rm {0}'.format(ipv6_patch(lab.CIRROS_BLD_DIR + '/cirros')))
        local('make ARCH=i386 br-source')
        local('make ARCH=x86_64 OUT_D={0}/output/i386 > LOG'.format(lab.CIRROS_BLD_DIR + '/cirros'))


def ipv6_patch(where=lab.HOME_DIR):
    """Generate IPv6 patch in the given dir"""
    patch = '''
=== modified file 'conf/busybox.config'
--- conf/busybox.config 2014-09-08 08:42:12 +0000
+++ conf/busybox.config 2014-12-05 14:17:26 +0000
@@ -730,7 +730,7 @@
 CONFIG_NC_EXTRA=y
 CONFIG_NC_110_COMPAT=y
 CONFIG_PING=y
-# CONFIG_PING6 is not set
+CONFIG_PING6=y
 CONFIG_FEATURE_FANCY_PING=y
 CONFIG_WHOIS=y
 CONFIG_FEATURE_IPV6=y
@@ -833,13 +833,13 @@
 # CONFIG_FEATURE_TFTP_PROGRESS_BAR is not set
 # CONFIG_TFTP_DEBUG is not set
 CONFIG_TRACEROUTE=y
-# CONFIG_TRACEROUTE6 is not set
+CONFIG_TRACEROUTE6=y
 # CONFIG_FEATURE_TRACEROUTE_VERBOSE is not set
 # CONFIG_FEATURE_TRACEROUTE_SOURCE_ROUTE is not set
 # CONFIG_FEATURE_TRACEROUTE_USE_ICMP is not set
 # CONFIG_TUNCTL is not set
 # CONFIG_FEATURE_TUNCTL_UG is not set
-# CONFIG_UDHCPC6 is not set
+CONFIG_UDHCPC6=y
 # CONFIG_UDHCPD is not set
 # CONFIG_DHCPRELAY is not set
 # CONFIG_DUMPLEASES is not set
'''
    file_name = where + '/ipv6.patch'
    with open(file_name, 'w') as f:
        f.write(patch)
    return file_name
