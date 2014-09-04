#!/usr/bin/env python

from __future__ import print_function
import argparse
from fabric import api
from fabric.contrib import files
import random
import string
import sys

TEMPEST_FILE_XML = 'tempest_results.xml'
TEMPEST_FILE_SUBUNIT = 'tempest_results.subunit'
TEMPEST_SUBUNIT_CMD = 'testr last --subunit > ' + TEMPEST_FILE_SUBUNIT
TEMPEST_XML_CMD = 'testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=' + TEMPEST_FILE_XML


def main(host, user, password, tempest_filter, tempest_dir, tempest_list_file,
         tempest_repo, tempest_branch, is_venv):
    cmd = './run_tempest.sh {venv} -- {filter_or_list}'.format(
        venv='-V' if is_venv else '-N',
        filter_or_list='--load-list=list.txt' if tempest_list_file else tempest_filter)
    settings = {'host_string': host,
                'user': user,
                'password': password,
                'warn_only': True}
    with api.settings(**settings):
        with api.cd(tempest_dir):
            random_name = ''.join(random.choice(string.lowercase) for _ in range(5))
            api.run('git remote add {name} {repo}'.format(name=random_name, repo=tempest_repo))
            api.run('git fetch {name} && git checkout -b {branch} {name}/{branch}'.format(name=random_name, branch=tempest_branch))
            if tempest_list_file:
                api.put(local_path=tempest_list_file, remote_path='list.txt')
            api.sudo(command='pip install junitxml')
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


def define_cli(p):
    p.name = 'run_tempest'
    p.description = 'runs tempest on remote host'
    p.add_argument('-r', '--remote', required=True,
                   help='ip address of host where tempest is deployed')
    p.add_argument('-u', '--user', default='localadmin')
    p.add_argument('-p', '--password', default='ubuntu')
    p.add_argument('-d', '--dir', default='/opt/stack/tempest')
    p.add_argument('-v', '--venv', default=False, type=bool, help='use venv?')
    p.add_argument('--repo', default='https://github.com/CiscoSystems/tempest.git', help='tempest repo')
    p.add_argument('--branch', default='master-in-use', help='tempest branch')
    p.add_argument('-f', '--filter', default='',
                   help='filter to choose a set of tests to be run')
    p.add_argument('-l', '--list', default=None, type=file,
                   help='file with list of tests, overrides --filter')

    def main_with_args(args):
        main(host=args.remote, user=args.user, password=args.password,
             tempest_filter=args.filter, tempest_list_file=args.list,
             tempest_dir=args.dir, is_venv=args.venv,
             tempest_repo=args.repo, tempest_branch=args.branch)

    p.set_defaults(func=main_with_args)


if __name__ == '__main__':
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    define_cli(p)
    args = p.parse_args()
    args.func(args)
