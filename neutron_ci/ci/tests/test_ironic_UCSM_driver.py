# Copyright 2016 Cisco Systems, Inc.
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

from __future__ import print_function

from ci.lib import test_ironic


class IronicCIMCDriverTestCase(test_ironic.IronicTestCase):

    enabled_driver = "pxe_ucs"

    def test_tempest(self):
        self.start_devstack()

        # Update ironic node to use UCSM driver
        (result, code) = self.run_cmd_with_openrc(
            'ironic node-update node-0 add '
            'properties/capabilities=\"boot_option:local\""')

        # Update nova flavor to enable local boot
        (result, code) = self.run_cmd_with_openrc(
            'nova flavor-key baremetal set '
            'capabilities:boot_option=\"local\""')

        self.run_ironic_tempest()
