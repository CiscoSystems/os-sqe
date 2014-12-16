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

TOPOLOGIES_DIR = os.path.abspath(os.path.join(REPO_DIR, 'fabs/lab/topologies'))
IMAGES_DIR = os.path.abspath(os.path.join(HOME_DIR, 'images'))
DISKS_DIR = os.path.abspath(os.path.join(HOME_DIR, 'disks'))
CIRROS_CONFIG = os.path.abspath(os.path.join(TOPOLOGIES_DIR, 'cirros_image.cfg'))
CIRROS_BLD_DIR = os.path.abspath(os.path.join(HOME_DIR, 'BLD'))
CIRROS_BUILD_ROOT_URL='http://buildroot.org/downloads/buildroot-2014.11.tar.gz'
CIRROS_KERNEL_URL='http://kernel.ubuntu.com/~kernel-ppa/mainline/v3.17.4-vivid/linux-image-3.17.4-031704-generic_3.17.4-031704.201411211317_amd64.deb'

def make_tmp_dir(local_dir):
    with settings(warn_only=False):
        local('mkdir -p ' + local_dir)


def wget_file(local_dir, file_url):
    from fabric.api import local

    file_local = os.path.abspath(os.path.join(local_dir, file_url.split('/')[-1]))
    make_tmp_dir(local_dir=local_dir)
    local('test -e  {file_local} || wget -nv {url} -O {file_local}'.format(url=file_url, file_local=file_local))
    return file_local
