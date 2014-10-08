# Copyright 2014 Cisco Systems, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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

DESCRIPTION = 'generate all possible parameter combinations for IPV6 testing'


def main():
    from metacomm.combinatorics.all_pairs2 import all_pairs2 as all_pairs

    params = {'AddressMode': ['SLAAC', 'DHCP6 stateless', 'DHCP6 statefull'],
              'Switch': ['InternalL2', 'ExternalL2'],
              'Router': ['InternalL3', 'ExternalL3'],
              'Security': ['SecNo', 'SecVPN', 'SecFirewall'],
              'Net': ['Only6', '64']}

    def is_valid_combination(vector):
        if 'SLAAC' in vector and 'ExternalL3' in vector:
            return False
        else:
            return True
    for i, kv in enumerate(params.iteritems(), start=1):
        print 'Test dimension {0}: {1}\t Possible values: {2}'.format(i, kv[0], kv[1])
    pairwise = all_pairs(params.values(), filter_func=is_valid_combination)
    for i, v in enumerate(pairwise, start=1):
        print 'Test {0}:\t{1}'.format(i, v)


def define_cli(p):
    def main_with_args(args):
        return main()

    p.set_defaults(func=main_with_args)
