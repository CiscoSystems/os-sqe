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
# @author: Nikolay Fedotov, Cisco Systems, Inc.

import argparse
import json
import requests
import urlparse
import os
from fabric.api import run, cd, env

parser = argparse.ArgumentParser()
parser.add_argument('--build-url', required=True)
parser.add_argument('--host', required=True)
parser.add_argument('--login', required=True)
parser.add_argument('--password', required=True)
parser.add_argument('--path', required=True)

if __name__ == '__main__':
    args = parser.parse_args()

    env.disable_known_hosts = True
    env.host_string = args.host
    env.user = args.login
    env.password = args.password
    build_url = args.build_url
    path = args.path

    response = requests.get(urlparse.urljoin(build_url, 'api/json'))
    json_data = json.loads(response.text)

    if 'artifacts' not in json_data:
        raise Exception('No artifacts found. Nothing to download.')

    run('[ ! -d "{p}" ] && mkdir -p "{p}"'.format(p=path), warn_only=True)
    with cd(path):
        # Create directories
        dirs = list()
        for a in json_data['artifacts']:
            d = os.path.dirname(a['relativePath'])
            if d and d not in dirs:
                run('mkdir -p "{d}"'.format(d=d))
                dirs.append(d)
        # Download artifacts
        for a in json_data['artifacts']:
            dest = a['relativePath']
            rel_url = 'artifact/{0}'.format(a['relativePath'])
            url = urlparse.urljoin(build_url, rel_url)
            run('wget {url} -O {dest}'.format(url=url, dest=dest),
                warn_only=True)
        # gzip files
        run('gzip -9 *', warn_only=True)
        for d in dirs:
            run('gzip -9 {d}/*'.format(d=d), warn_only=True)
