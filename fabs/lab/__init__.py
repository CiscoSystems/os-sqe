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
import os
from fabric.api import local, settings
from fabs import REPO_DIR, HOME_DIR
from fabs import decorators

TOPOLOGIES_DIR = os.path.abspath(os.path.join(REPO_DIR, 'fabs/lab/topologies'))
DEVSTACK_CONF_DIR = os.path.abspath(os.path.join(TOPOLOGIES_DIR, 'devstack'))
PACKSTACK_CONF_DIR = os.path.abspath(os.path.join(TOPOLOGIES_DIR, 'packstack'))
TEMPEST_CONF_DIR = os.path.abspath(os.path.join(TOPOLOGIES_DIR, 'tempest'))
IMAGES_DIR = os.path.abspath(os.path.join(HOME_DIR, 'images'))
DISKS_DIR = os.path.abspath(os.path.join(HOME_DIR, 'disks'))
XMLS_DIR = os.path.abspath(os.path.join(HOME_DIR, 'xml'))

CIRROS_BLD_DIR = os.path.abspath(os.path.join(HOME_DIR, 'BLD'))
CIRROS_BUILD_ROOT_URL='http://buildroot.org/downloads/buildroot-2014.11.tar.gz'
CIRROS_KERNEL_URL='http://kernel.ubuntu.com/~kernel-ppa/mainline/v3.17.4-vivid/linux-image-3.17.4-031704-generic_3.17.4-031704.201411211317_amd64.deb'
CIRROS_CONFIGS_DIR = os.path.abspath(os.path.join(REPO_DIR, 'fabs/lab/topologies'))


def make_tmp_dir(local_dir):
    with settings(warn_only=False):
        local('mkdir -p ' + local_dir)


def wget_file(local_dir, file_url):
    file_local = os.path.abspath(os.path.join(local_dir, file_url.split('/')[-1]))
    with settings(warn_only=False):
        make_tmp_dir(local_dir=local_dir)
        local('test -e  {file_local} || wget -nv {url} -O {file_local}'.format(url=file_url, file_local=file_local))
        return file_local


@decorators.repeat_until_not_false(n_repetitions=50, time_between_repetitions=5)
def ip_for_mac_by_looking_at_libvirt_leases(net, mac):
    with settings(warn_only=True):
        ans = local('sudo grep "{mac}" /var/lib/libvirt/dnsmasq/{net}.leases'.format(mac=mac, net=net), capture=True)
        if ans:
            return ans.split(' ')[2]
        else:
            return ans


def ip_for_mac_and_prefix(mac, prefix):
    import netaddr

    if netaddr.valid_ipv4(prefix):
        raise TypeError('Unable to generate IP address by EUI64 for IPv4 prefix')
    try:
        eui64 = int(netaddr.EUI(mac).eui64())
        prefix = netaddr.IPNetwork(prefix)
        return str(netaddr.IPAddress(prefix.first + eui64 ^ (1 << 57)))
    except (ValueError, netaddr.AddrFormatError):
        raise TypeError('Bad prefix ({0}) or mac ({1}) for IPv6 '.format(prefix, mac))
