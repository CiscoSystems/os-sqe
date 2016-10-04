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
from fabric.api import task


@task
def read_via_xml_api(host='172.31.229.169', username='admin', password='cisco123'):
    """Returns json describing current status of UCS via cimc"""
    import requests

    with requests.Session() as s:
        # req = requests.Request('POST', 'http://{}/nuova'.format(host), data={}, headers={})
        # prep = s.prepare_request(req)
        # prep.body = '<aaaLogin inName="{0}" inPassword="{1}"/>'.format(username, password)
        h = {'Content-Type': 'application/x-www-form-urlencoded'}
        body = '<aaaLogin inName="{0}" inPassword="{1}"/>'.format(username, password)
        r = s.put('https://{}/nuova'.format(host), verify=False, data=body, headers=h)
        print r
