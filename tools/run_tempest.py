#!/usr/bin/env python

from __future__ import print_function
import argparse
from fabric import api
from fabric.contrib import files
import random
import string
from deployers import utils

TEMPEST_FILE_XML = 'tempest_results.xml'
TEMPEST_FILE_SUBUNIT = 'tempest_results.subunit'
TEMPEST_SUBUNIT_CMD = 'testr last --subunit > ' + TEMPEST_FILE_SUBUNIT
TEMPEST_XML_CMD = 'testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=' + TEMPEST_FILE_XML
SCREEN_LOGDIR = '/opt/stack/logs/'

def main(host, user, password, tempest_filter, tempest_dir, tempest_list_file,
         tempest_repo, tempest_branch, is_venv, wait_time=0, kill_time=0,
         test_time='', patch_set=None):
    cmd = './run_tempest.sh {venv} -- {filter_or_list}'.format(
        venv='-V' if is_venv else '-N',
        filter_or_list='--load-list=list.txt' if tempest_list_file else tempest_filter)
    if wait_time and kill_time:
        cmd = "timeout --preserve-status -s 2 -k {kill_time} {wait_time} ".format(kill_time=kill_time, wait_time=wait_time) + cmd
    if test_time:
        cmd = 'export OS_TEST_TIMEOUT={test_time}; '.format(test_time=test_time) + cmd
    settings = {'host_string': host,
                'user': user,
                'password': password,
                'warn_only': True}
    with api.settings(**settings):
        with api.cd(tempest_dir):
            random_name = ''.join(random.choice(string.lowercase) for _ in range(5))
            api.run('git remote add {name} {repo}'.format(name=random_name, repo=tempest_repo))
            api.run('git fetch {name} {branch} && git checkout -b {name}_{branch} {name}/{branch}'.format(
                name=random_name,
                branch=tempest_branch))
            if tempest_list_file:
                api.put(local_path=tempest_list_file, remote_path='list.txt')
            api.sudo(command='pip install junitxml')
            if patch_set:
                api.run('git fetch https://review.openstack.org/openstack/tempest'
                        ' {0} && git checkout FETCH_HEAD'.format(patch_set))
            api.run(command='testr init')
            api.run(command=cmd)
            api.run(command=TEMPEST_SUBUNIT_CMD)
            api.run(command=TEMPEST_XML_CMD)
            if files.exists(path=TEMPEST_FILE_XML):
                api.get(remote_path=TEMPEST_FILE_XML, local_path=TEMPEST_FILE_XML)
                api.run('rm ' + TEMPEST_FILE_XML)
            else:
                print(TEMPEST_FILE_XML + ' is not created on remote', file=sys.stderr)
            if files.exists(path=TEMPEST_FILE_SUBUNIT):
                api.get(remote_path=TEMPEST_FILE_SUBUNIT, local_path=TEMPEST_FILE_SUBUNIT)
                api.run('rm ' + TEMPEST_FILE_SUBUNIT)
            else:
                print(TEMPEST_FILE_SUBUNIT + ' is not created on remote', file=sys.stderr)
            utils.collect_logs_devstack("test_run")

DESCRIPTION = 'run tempest on the given remote host'


def patch_set_validator(patch_set):
    import re

    if not patch_set or re.match('^refs/changes/\d+/\d+/\d+$', patch_set):
        return patch_set
    else:
        raise argparse.ArgumentTypeError('expect something like refs/changes/44/129144/1')


def define_cli(p):
    repo = 'https://github.com/CiscoSystems/tempest.git'
    branch = 'ipv6'
    p.add_argument('-r', '--remote', required=True,
                   help='ip address of DNS name of the host where tempest is deployed')
    p.add_argument('-u', '--user', default='localadmin',
                   help='user name on the remote')
    p.add_argument('-p', '--password', default='ubuntu',
                   help='user password on the remote')
    p.add_argument('-d', '--dir', default='/opt/stack/tempest',
                   help='folder where tempeset is deployed')
    p.add_argument('-v', '--venv', action='store_true',
                   help='switch usage of python venv on/off')
    p.add_argument('--repo', nargs='?', const=repo, default=repo, help='tempest repo')
    p.add_argument('--branch', nargs='?', const=branch, default=branch, help='tempest branch')
    p.add_argument('-f', '--filter', default='',
                   help='filter to choose a set of tests to be run')
    p.add_argument('-l', '--list', default=None, type=file,
                   help='file with list of tests, overrides --filter')
    p.add_argument('--wait_time', default=0,
                   help='Wait time for script execution timeout')
    p.add_argument('--kill_time', default=0,
                   help='Kill time for script execution timeout')
    p.add_argument('--test_time', nargs='?', const='', default='',
                   help='Maximal time for test execution')
    p.add_argument('--patchset', nargs='?', const='', type=patch_set_validator,
                   default='', help='Custom patch set in form refs/changes/44/129144/1')

    def main_with_args(args):
        main(host=args.remote, user=args.user, password=args.password,
             tempest_filter=args.filter, tempest_list_file=args.list,
             tempest_dir=args.dir, is_venv=args.venv,
             tempest_repo=args.repo, tempest_branch=args.branch,
             wait_time=args.wait_time, kill_time=args.kill_time,
             test_time=args.test_time, patch_set=args.patchset)

    p.set_defaults(func=main_with_args)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=DESCRIPTION,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    define_cli(p)
    args = p.parse_args()
    args.func(args)
