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

import logging
import os
import StringIO
from fabric.api import cd, run, put
from fabric.contrib.files import exists
from fabric.context_managers import settings
from fabric.operations import get, local
from ci import WORKSPACE, BUILD_LOG_PATH, PARENT_FOLDER_PATH


logger = logging.getLogger(__name__)


class DevStack(object):

    def __init__(self, host_string='localhost', localrc=None, local_conf=None,
                 git_url='https://github.com/openstack-dev/devstack.git',
                 git_branch='master',
                 clone_path='~/devstack'):
        # host_string value of fabric env dictionary
        self.host_string = host_string

        self._git_url = git_url
        self._git_branch = git_branch
        self._clone_path = os.path.expanduser(clone_path)

        self.localrc = localrc
        self.local_conf = local_conf
        self.localrc_path = os.path.join(self._clone_path, 'localrc')
        self.localconf_path = os.path.join(self._clone_path, 'local.conf')

        self._tempest_path = '/opt/stack/tempest'

    def clone(self, commit=None, force=False):
        logger.info('Clone DevStack to {0}'.format(self._clone_path))
        with settings(host_string=self.host_string):
            if exists(self._clone_path):
                if force:
                    logger.info('{0} already exists. Remove it.'
                                ''.format(self._clone_path))
                    run('rm -rf {0}'.format(self._clone_path))
                else:
                    logger.error('{0} already exists.'
                                 ''.format(self._clone_path))
                    return
            cmd = 'git clone -q -b {branch} {url} {dest}'.format(
                branch=self._git_branch, url=self._git_url,
                dest=self._clone_path)
            output = run(cmd)
            logger.info(output)

            if commit:
                with cd(self._clone_path):
                    output = run('git checkout {commit}'.format(commit=commit))
                    logger.info(output)

    def _put_localrc(self):
        if self.localrc is None:
            return
        logger.info('Writing localrc file to {0}'.format(self.localrc_path))
        logger.debug(self.localrc)
        with settings(host_string=self.host_string):
            localrc_io = StringIO.StringIO()
            localrc_io.write(self.localrc)
            put(localrc_io, self.localrc_path)

    def _put_local_conf(self):
        if self.local_conf is None:
            return
        logger.info('Writing local.conf file to {0}'
                    ''.format(self.localconf_path))
        logger.debug(self.local_conf)
        with settings(host_string=self.host_string):
            local_conf_io = StringIO.StringIO()
            local_conf_io.write(self.local_conf)
            put(local_conf_io, self.localconf_path)

    def patch(self, patch_path):
        logger.info('Patch devstack {0}'.format(patch_path))
        with open(patch_path) as f:
            logger.info(f.read())
        with settings(host_string=self.host_string):
            tmp_path = '/tmp/devstack.patch'
            with cd(self._clone_path):
                put(patch_path, tmp_path)
                run("git am --signoff < {p}".format(p=tmp_path))

    def download_gerrit_change(
            self, ref,
            gerrit='https://review.openstack.org/openstack-dev/devstack'):
        logger.info('Download gerrit ref {0}'.format(ref))
        with settings(host_string=self.host_string):
            with cd(self._clone_path):
                cmd = "git fetch {g} {ref} && " \
                      "git cherry-pick FETCH_HEAD" \
                      "".format(g=gerrit, ref=ref)
                run(cmd, shell=True)

    def stack(self):
        failed = False
        self._put_localrc()
        self._put_local_conf()

        logger.info('Launch stack.sh')
        with cd(self._clone_path), settings(warn_only=True,
                                            host_string=self.host_string):
            failed = run('./stack.sh').failed
        return failed

    def unstack(self):
        logger.info('Unstack')
        with cd(self._clone_path), settings(warn_only=True,
                                            host_string=self.host_string):
            run('if screen -ls | grep stack; then  ./unstack.sh; fi')

    def run_tempest(self, test_list_path):
        logger.info('Run tempest tests')
        logger.info('Tests to be run: {0}'.format(test_list_path))
        with open(test_list_path) as f:
                logger.info(f.read())

        failed = False
        with settings(host_string=self.host_string):
            temp_path = '/tmp/tempest_tests.txt'
            put(test_list_path, temp_path)

            with cd(self._tempest_path), settings(warn_only=True):
                if not exists('.testrepository'):
                    run('testr init')
                # Run tempest
                cmd = 'testr run --load-list="{tests_list}"' \
                      ''.format(tests_list=temp_path)
                failed = run(cmd).failed
        return failed

    def get_tempest_unitxml(self, path):
        with settings(host_string=self.host_string,
                      warn_only=True), cd(self._tempest_path):
            # Export tempest results to junit xml file
            junitxml_rem = '/tmp/tempest.xml'
            cmd = 'testr last --subunit | subunit-1to2 | subunit2junitxml ' \
                  '--output-to="{xml}"'.format(xml=junitxml_rem)
            run(cmd)
            get(junitxml_rem, path)

    def get_tempest_html(self, path):
        with settings(host_string=self.host_string,
                      warn_only=True), cd(self._tempest_path):
            subunit_rem = '/tmp/testr_results.subunit'
            subunit_loc = '/tmp/testr.subunit'
            html_path = os.path.join(path, 'testr_results.html')
            # Export tempest results to subunit file
            run('testr last --subunit > "{s}"'.format(s=subunit_rem))
            # download subunit file to temp folder
            get(subunit_rem, subunit_loc)

            # Convert subunit to html
            s2h = os.path.join(PARENT_FOLDER_PATH, 'tools/subunit2html.py')
            local('python {s2h} {s} {h}'.format(s2h=s2h, s=subunit_loc,
                                                h=html_path))

    def get_locals(self, path):
        with settings(host_string=self.host_string, warn_only=True):
            for v, p in ((self.localrc, self.localrc_path),
                         (self.local_conf, self.localconf_path)):
                if v is not None:
                    get(p, path)

    def get_screen_logs(self, path, SCREEN_LOGDIR='/opt/stack/screen-logs'):
        with settings(host_string=self.host_string, warn_only=True):
            p = '/tmp/logs'
            run('mkdir -p {p}'.format(p=p))
            run('find {sl} -type l -exec cp "{{}}" {p} '
                '\;'.format(sl=SCREEN_LOGDIR, p=p))
            get(p, path)

    def clear(self):
        with settings(host_string=self.host_string, warn_only=True):
            logger.info('Remove /opt/stack folder')
            run('sudo rm -rf /opt/stack')
            logger.info('Call "sudo apt-get autoremove"')
            run('sudo apt-get autoremove -y')

    def restart_ovs(self):
        with settings(host_string=self.host_string, warn_only=True):
            logger.info('Restart "openvswitch-switch"')
            run('sudo /etc/init.d/openvswitch-switch restart')

    def rsync_repositories(self, source_path):
        with settings(host_string=self.host_string, warn_only=True):
            run('rsync -arv {0} {1}'.format(source_path, '/opt/stack'))
