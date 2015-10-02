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

class WithStatusMixIn(object):
    def __repr__(self):
        attributes = vars(self)
        return '\n'.join(['{0}:\t{1}'.format(key, attributes[key]) for key in sorted(attributes.keys()) if not key.startswith('_')])

    def status(self):
        from logger import lab_logger
        lab_logger.info('status of {0}:\n{1}'.format(type(self), self))
