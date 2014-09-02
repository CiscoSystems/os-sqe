#!/usr/bin/env python

import argparse
from fabric import api
import os

TEMPEST_FILE_XML = 'tempest_results.xml'
TEMPEST_FILE_SUBUNIT = 'tempest_results.subunit'
TEMPEST_RUN_CMD = 'testr run --subunit {0} | subunit-2to1 | tools/colorizer.py'
TEMPEST_SUBUNIT_CMD = 'testr last --subunit > ' + TEMPEST_FILE_SUBUNIT
TEMPEST_XML_CMD = 'testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=' + TEMPEST_FILE_XML


def main(host, user, password, tempest_filter, tempest_dir, tempest_list_file):
    settings = {'host_string': host,
                'user': user,
                'password': password,
                'warn_only': True}
    with api.settings(**settings):
        with api.cd(tempest_dir):
            if tempest_list_file:
                api.put(local_path=tempest_list_file, remote_path='list.txt')
                cmd = TEMPEST_RUN_CMD.format('--load-list=list.txt')
            else:
                cmd = TEMPEST_RUN_CMD.format(tempest_filter)
            api.run(command=cmd)
            api.run(command=TEMPEST_SUBUNIT_CMD)
            api.run(command=TEMPEST_XML_CMD)
            api.get(remote_path=TEMPEST_FILE_XML, local_path=TEMPEST_FILE_XML)
            api.get(remote_path=TEMPEST_FILE_SUBUNIT, local_path=TEMPEST_FILE_SUBUNIT)


if __name__ == '__main__':
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('-r', '--remote', required=True,
                   help='ip address of host where tempest is deployed')
    p.add_argument('-u', '--user', default='localadmin')
    p.add_argument('-p', '--password', default='ubuntu')
    p.add_argument('-d', '--dir', default='/opt/stack/tempest')
    p.add_argument('-f', '--filter', default='',
                   help='filter to choose a set of tests to be run')
    p.add_argument('-l', '--list', default=None, type=file,
                   help='file with list of tests, overrides --filter')
    args = p.parse_args()
    main(host=args.remote, user=args.user, password=args.password,
         tempest_filter=args.filter, tempest_list_file=args.list,
         tempest_dir=args.dir)
