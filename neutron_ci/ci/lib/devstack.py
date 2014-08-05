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
import requests
from ci.lib import utils
from ci.jenkins_vars import WORKSPACE, JOB_LOG_PATH


logger = logging.getLogger(__name__)


class DevStack(object):

    def __init__(self, localrc=None, local_conf=None,
                 git_url='https://github.com/openstack-dev/devstack.git',
                 git_branch='master',
                 clone_path=os.path.join(WORKSPACE, 'devstack')):
        self.localrc = localrc
        self.local_conf = local_conf
        self._git_url = git_url
        self._git_branch = git_branch
        self._clone_path = os.path.expanduser(clone_path)
        self.localrc_path = os.path.join(self._clone_path, 'localrc')
        self.localconf_path = os.path.join(self._clone_path, 'local.conf')
        self._tempest_path = os.path.join('/opt/stack/', 'tempest')

    def clone(self, force=False):
        if os.path.exists(self._clone_path):
            if force:
                logger.info(
                    '{0} already exists. Remove it.'.format(self._clone_path))
                os.rmdir(self._clone_path)
            else:
                logger.error('{0} already exists.'.format(self._clone_path))
                return
        logger.info('Clone DevStack to {0}'.format(self._clone_path))
        cmd = 'git clone --depth=1 -b {branch} {url} {dest}'.format(
            branch=self._git_branch, url=self._git_url, dest=self._clone_path)
        output, code = utils.run_cmd_line(cmd)
        logger.info(output)

    def _put_localrc(self):
        if self.localrc is None:
            return
        logger.info('Writing localrc file to {0}'.format(self.localrc_path))
        with open(self.localrc_path, 'w') as localrc:
            localrc.write(self.localrc)
            logger.debug(self.localrc)

    def _put_local_conf(self):
        if self.local_conf is None:
            return
        logger.info(
            'Writing local.conf file to {0}'.format(self.localconf_path))
        with open(self.localconf_path, 'w') as local_conf:
            local_conf.write(self.local_conf)
            logger.debug(self.local_conf)

    def patch(self, patch_path):
        logger.info('Patch devstack {0}'.format(patch_path))
        try:
            os.chdir(self._clone_path)
            with open(patch_path) as f:
                logger.info(f.read())
            cmd = "git am --signoff < {p}".format(p=patch_path)
            utils.run_cmd_line(cmd, shell=True)
        except Exception as e:
            logger.error(e)
        finally:
            os.chdir(WORKSPACE)

    def stack(self):
        code = 0
        try:
            self._put_localrc()
            self._put_local_conf()

            logger.info('Launch stack.sh')
            os.chdir(self._clone_path)
            output, code = utils.run_cmd_line(
                './stack.sh', check_result=False, shell=True)
        except Exception as e:
            logger.error(e)
        finally:
            os.chdir(WORKSPACE)
        return code

    def run_tempest(self, test_list_path):
        logger.info('Run tempest tests')
        logger.info('Tests to be run: {0}'.format(test_list_path))
        code = 0
        with open(test_list_path) as f:
            logger.info(f.read())

        try:
            os.chdir('/opt/stack/tempest')
            if not os.path.isdir('.testrepository'):
                utils.run_cmd_line(
                    'testr init', check_result=False, shell=True)

            # Run tempest
            cmd = 'testr run --load-list="{tests_list}" --subunit | ' \
                  'subunit-2to1 | tools/colorizer.py ' \
                  '|| :'.format(tests_list=test_list_path)
            output, code = utils.run_cmd_line(
                cmd, check_result=False, shell=True)

            self.tempest_last2junitxml()
            self.tempest_last2html()
        except Exception as e:
            logger.error(e)
        finally:
            os.chdir(WORKSPACE)
        return code

    def tempest_last2junitxml(self):
        try:
            junitxml_path = os.path.join(JOB_LOG_PATH, 'tempest.xml')
            os.chdir(self._tempest_path)
            cmd = 'testr last --subunit | subunit-1to2 | subunit2junitxml ' \
                  '--output-to="{xml}"'.format(xml=junitxml_path)
            utils.run_cmd_line(cmd, shell=True)
        except Exception as e:
            logger.error(e)
        finally:
            os.chdir(WORKSPACE)

    def tempest_last2html(self):
        try:
            subunit_path = os.path.join(WORKSPACE, 'testr_results.subunit')
            html_path = os.path.join(JOB_LOG_PATH, 'testr_results.html')
            subunit2html_path = os.path.join(WORKSPACE, 'subunit2html.py')

            # Export tempest results to subunit file
            os.chdir(self._tempest_path)
            utils.run_cmd_line(
                'testr last --subunit > "{s}"'.format(s=subunit_path),
                shell=True)
            os.chdir(WORKSPACE)

            # Convert subunit to html
            with open(subunit2html_path, 'w') as f:
                url = 'wget https://raw.githubusercontent.com/' \
                      'openstack-infra/config/master/modules/' \
                      'openstack_project/files/slave_scripts/subunit2html.py'
                r = requests.get(url)
                f.write(r.text)

            utils.run_cmd_line(
                'python {s2h} {s} {h}'
                ''.format(s2h=subunit2html_path, s=subunit_path, h=html_path),
                shell=True)
        except Exception as e:
            logger.error(e)
        finally:
            os.chdir(WORKSPACE)
