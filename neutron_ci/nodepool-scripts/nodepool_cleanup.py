#!/usr/bin/env python

# Copyright 2016 Cisco Systems, Inc.
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
# @author: Yaroslav Morkovnikov, Cisco Systems, Inc.
#
# We are going to clean up all nodepool nodes

import re
import subprocess

def main():
    nodepool_output=subprocess.Popen("nodepool list", shell = True, stdout = subprocess.PIPE).communicate()[0]
    for node_id in re.findall('[| ]\d{1,10}[ | ]', nodepool_output):
        node_id = "nodepool delete --now" + node_id
        subprocess.call(node_id, shell=True)

if __name__ == '__main__':
    main()
