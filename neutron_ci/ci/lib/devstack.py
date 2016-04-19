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
import time
from fabric.api import cd, run, put
from fabric.contrib.files import exists
from fabric.context_managers import settings
from fabric.operations import get, local
from ci import PARENT_FOLDER_PATH


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
        self._cloned_repos_path = os.path.expanduser('~/os_repos/')

        self.localrc = localrc
        self.local_conf = local_conf
        self.localrc_path = os.path.join(self._clone_path, 'localrc')
        self.localconf_path = os.path.join(self._clone_path, 'local.conf')

        self._tempest_path = '/opt/stack/tempest'

    @property
    def tempest_conf(self):
        return os.path.join(self._tempest_path, 'etc/tempest.conf')

    def clone(self, commit=None, force=True):
        logger.info('Clone DevStack to {0}'.format(self._clone_path))
        with settings(host_string=self.host_string):
            if exists(self._clone_path):
                if force:
                    logger.info('{0} already exists. Remove it.'
                                ''.format(self._clone_path))
                    logger.info(run('rm -vrf {0}'.format(self._clone_path)))
                else:
                    logger.error('{0} already exists.'
                                 ''.format(self._clone_path))
                    return
            cmd = 'git clone -q -b {branch} {url} {dest}'.format(
                branch=self._git_branch, url=self._git_url,
                dest=self._clone_path)
            run(cmd)

            with cd(self._clone_path):
                if commit:
                    output = run('git checkout {commit}'.format(commit=commit))
                    logger.info(output)
                logger.info(run('git --no-pager log -n1'))

    def _put_localrc(self):
        if self.localrc is None:
            return
        logger.info('Writing localrc file to {0}'.format(self.localrc_path))
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
        self._put_localrc()
        self._put_local_conf()

        logger.info('Launch stack.sh')
        with cd(self._clone_path), settings(warn_only=True,
                                            host_string=self.host_string):
            res = run('./stack.sh')
            #logger.info(res)
        return res.failed

    def unstack(self):
        logger.info('Unstack')
        with cd(self._clone_path), settings(warn_only=True,
                                            host_string=self.host_string):
            run('if screen -ls | grep stack; then  ./unstack.sh; fi')

    def update_ini(self, ini_path, ini_params):
        """
        Update ini file using 'crudini' tool
        :param ini_path:
        :param ini_params: Dictionary {<section1>: {<param1>: <value1>, <param2>: <value2>},
                                    <section2>: {<param1>: <value1>}}
        :return:
        """
        with settings(host_string=self.host_string):
            # TODO: remove it later
            run('sudo apt-get -y install crudini')
            for section, params in ini_params.iteritems():
                for param, value in params.iteritems():
                    cmd = "crudini --set {file} {section} {param} '{value}'".format(
                        file=ini_path, section=section, param=param, value=value)
                    run(cmd)

    def get_ini(self, ini_path, ini_params):
        """
        Update ini file using 'crudini' tool
        :param ini_path:
        :param ini_params: Dictionary {<section1>: [<param1>, <param2>],
                                    <section2>: [<param1>]}
        :return:
        """
        with settings(host_string=self.host_string):
            # TODO: remove it later
            run('sudo apt-get -y install crudini')

            res = {}
            for section, params in ini_params.iteritems():
                if section not in res:
                    res[section] = dict()
                for param in params:
                    cmd = 'crudini --get --format=ini {file} {section} {param}'.format(
                        file=ini_path, section=section, param=param)
                    name, value = run(cmd).stdout.split('=')
                    res[section][name.strip()] = value.strip()
            return res

    def get_tempest(self, destination, tempest_repo, tempest_branch,
                    tempest_config, tempest_config_params=None):
        with settings(host_string=self.host_string):
            if exists(destination):
                logger.info('{0} already exists. Remove it.'
                            ''.format(destination))
                run('rm -rf {0}'.format(destination))

            cmd = 'git clone --depth=1 -q -b {branch} {url} {dest}'.format(
                branch=tempest_branch, url=tempest_repo,
                dest=destination)
            output = run(cmd)
            logger.info(output)
            self._tempest_path = destination

            # copy and update tempest conf
            with cd(destination):
                run('cp {0} {1}'.format(tempest_config, self.tempest_conf))
                if tempest_config_params:
                    self.update_ini(self.tempest_conf, tempest_config_params)

    def run_tempest(self, *args, **kwargs):
        logger.info('Run tempest tests')

        test_list_path = kwargs.get('test_list_path')
        all_plugin = kwargs.get('all_plugin', False) is True
        env_args = kwargs.get('env_args', {})
        testr_args = ' '.join(args)
        with settings(host_string=self.host_string):
            if test_list_path:
                temp_path = '/tmp/tempest_tests.txt'
                put(test_list_path, temp_path)
                testr_args += ' --load-list="{tests_list}"'.format(
                    tests_list=temp_path)

            with cd(self._tempest_path), settings(warn_only=True):
                envs = ''
                for k, v in env_args.items():
                    envs += "%s=%s " % (k, v)

                if not envs:
                    cmd = 'tox'
                else:
                    cmd = 'env %s tox' % envs.strip()

                if all_plugin:
                    cmd += ' -eall-plugin'
                else:
                    cmd += ' -eall'

                cmd += ' -- {0}'.format(testr_args)

                # Run tempest
                res = run(cmd)
                logger.info(res)
        return res.failed

    def get_tempest_unitxml(self, path, file_name='tempest.xml'):
        with settings(host_string=self.host_string,
                      warn_only=True), cd(self._tempest_path):
            # Export tempest results to junit xml file
            junitxml_rem = os.path.join('/tmp', file_name)
            cmd = 'testr last --subunit | subunit-1to2 | subunit2junitxml ' \
                  '--output-to="{xml}"'.format(xml=junitxml_rem)
            run(cmd)
            get(junitxml_rem, path)

    def get_tempest_html(self, path, file_name='testr_results.html'):
        with settings(host_string=self.host_string,
                      warn_only=True), cd(self._tempest_path):
            subunit_rem = '/tmp/testr_results.subunit'
            subunit_loc = '/tmp/testr.subunit'
            html_path = os.path.join(path, file_name)
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
            logger.info('Remove ~/.cache folder')
            logger.info(run('sudo rm -rf ~/.cache'))
            logger.info('Call "sudo apt-get autoremove"')
            logger.info(run('sudo apt-get autoremove -y'))
            logger.info(run('sudo dpkg --configure -a'))

    def clear_stack_folder(self):
        with settings(host_string=self.host_string, warn_only=True):
            logger.info('Remove /opt/stack folder')
            run('sudo rm -vrf /opt/stack')

    def restart_ovs(self):
        with settings(host_string=self.host_string, warn_only=True):
            logger.info('Restart "openvswitch-switch"')
            run('sudo /etc/init.d/openvswitch-switch restart')

    def clone_repositories(self, dest):
        with settings(host_string=self.host_string, warn_only=True):
            logger.info('Clone openstack repositories to {0}'.format(dest))
            if not exists(dest):
                cmd = "{0} {1}".format(
                    os.path.join(PARENT_FOLDER_PATH,
                                 'nodepool-scripts/clone_repositories.sh'),
                    dest)
                run(cmd)
            else:
                logger.warn('Folder already exists {0}, aborting'.format(dest))

    def rsync_repositories(self, source_path):
        dest = '/opt/stack'
        with settings(host_string=self.host_string, warn_only=True):
            if not exists(dest):
                logger.info('rsync openstack repositories')
                run('sudo mkdir {0}'.format(dest))
                run('sudo chown $(whoami) {0}'.format(dest))
                run('rsync -arv {0} {1}'.format(source_path, dest))
                run('sudo chown -R $(whoami) {0}'.format(dest))
            else:
                logger.warn('Folder already exists {0}, aborting'.format(dest))

    def screen_session_name(self):
        with settings(host_string=self.host_string, warn_only=True):
            return run('screen -ls | grep -P -o "\d+\.stack"')

    def rejoin(self, wait=30):
        session_name = self.screen_session_name()
        if session_name:
            with settings(host_string=self.host_string,
                          warn_only=True), cd(self._clone_path):
                run('screen -X -S {0} quit'.format(session_name))
                run('./rejoin-stack.sh')
                time.sleep(wait)

    def brew_repo(self, project, ref, merge_refs):
        logger.info('Brewing repo {0}, ref {1}, merge {2}'.format(
            project, ref, merge_refs))
        path = os.path.join('/tmp/', project)
        review_url = 'https://review.openstack.org/' + project
        repo_url = 'https://git.openstack.org/' + project + '.git'
        branch = 'testing'
        with settings(host_string=self.host_string):
            if exists(path):
                run('rm -vrf {0}'.format(path))
            run('mkdir -p {0}'.format(path))
            with cd(path):
                logger.info(run('git clone {} .'.format(repo_url)))
                logger.info(run('git fetch origin {0}'.format(ref)))
                logger.info(run('git checkout FETCH_HEAD'))
                logger.info(run('git checkout -b {0}'.format(branch)))
                for merge_ref in merge_refs:
                    logger.info(run('git fetch {0} {1}'.format(
                        review_url, merge_ref)))
                    logger.info(run('git merge FETCH_HEAD'))
                logger.info(run('git log --pretty=oneline -n{}'.format(
                    len(merge_refs) + 1)))

        return path, branch

    def kill_python_apps(self):
        logger.info('Kill python apps')
        with settings(host_string=self.host_string, warn_only=True):
            run("for pid in `ps -ef | grep python | "
                "awk '{print $2}'`; do  sudo kill -9 $pid; done")
