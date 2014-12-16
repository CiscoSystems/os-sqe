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

from fabric.api import task
from fabs.common import timed
from fabs.lab.cirros_builders import build_new, build_old

__all__ = ['build', 'build_old']


@task
@timed
def build():
    """Build cirros image using build root tool only"""
    build_new()


@task
@timed
def build_old():
    """Build cirros image using the way suggested by current cirros maintainer"""
    build_old()
