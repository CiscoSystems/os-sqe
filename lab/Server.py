# Copyright 2014 Cisco Systems, Inc.
# All Rights Reserved.
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

class Server(object):
    def __init__(self, ip, username, password, hostname='Unknown',
                 ssh_public_key='N/A', ssh_port=22,
                 ipmi_ip=None, ipmi_username=None, ipmi_password=None,
                 pxe_mac=None, ip_mac=None):
        self.ip = ip
        self.ip_mac = ip_mac
        self.hostname = hostname
        self.username = username
        self.password = password
        self.ssh_public_key = ssh_public_key
        self.ssh_port = ssh_port

        self.ipmi_ip = ipmi_ip
        self.ipmi_username = ipmi_username
        self.ipmi_password = ipmi_password
        self.pxe_mac = pxe_mac

    def __repr__(self):
        return 'sshpass -p {0} ssh {1}@{2}'.format(self.password, self.username, self.ip)
