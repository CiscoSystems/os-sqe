# Copyright 2014 Cisco Systems, Inc.
#
# Connect to the Nexus switch with IP address as specified on the
# command line and disable the specified VLANs from the specified
# ethernet interface, and remove the VLANs from the router.
#
# @author: Dane LeBlanc, Cisco Systems, Inc.

import sys
import os
import warnings
from ncclient import manager
from ncclient import operations

warnings.simplefilter("ignore", DeprecationWarning)

exec_conf_prefix = """
      <config xmlns:xc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <configure xmlns="http://www.cisco.com/nxos:1.0:vlan_mgr_cli">
          <__XML__MODE__exec_configure>
"""

exec_conf_suffix = """
          </__XML__MODE__exec_configure>
        </configure>
      </config>
"""

cmd_no_vlan_conf_snippet = """
          <no>
            <vlan>
              <vlan-id-create-delete>
                <__XML__PARAM_value>%s</__XML__PARAM_value>
              </vlan-id-create-delete>
            </vlan>
          </no>
"""

cmd_no_vlan_int_snippet = """
          <interface>
            <ethernet>
              <interface>%s</interface>
              <__XML__MODE_if-ethernet-switch>
                <switchport>
                  <trunk>
                    <allowed>
                      <vlan>
                        <remove>
                          <vlan>%s</vlan>
                        </remove>
                      </vlan>
                    </allowed>
                  </trunk>
                </switchport>
              </__XML__MODE_if-ethernet-switch>
            </ethernet>
          </interface>
"""


def nxos_connect(host, port, user, password):
    return manager.connect(host=host, port=port, username=user,
                           password=password)


def cmd_encap(confstr):
    return exec_conf_prefix + confstr + exec_conf_suffix


def remove_vlan(mgr, vlan):
    confstr = cmd_encap(cmd_no_vlan_conf_snippet % vlan)
    mgr.edit_config(target='running', config=confstr)


def disable_vlan_on_trunk_int(mgr, intf_num, vlan):
    confstr = cmd_encap(cmd_no_vlan_int_snippet % (intf_num, vlan))
    mgr.edit_config(target='running', config=confstr)


def clear_nexus_config(host, user, password, intf_num, vlan_start, vlan_end):
    vlan_id_start = int(vlan_start)
    vlan_id_end = int(vlan_end)
    num_vlans = vlan_id_end - vlan_id_start + 1
    if num_vlans > 100:
        print_usage()
        sys.exit(1)
    print "Disabling VLANs %s-%s on ethernet %s and removing from switch." % (
        vlan_start, vlan_end, intf_num)
    with nxos_connect(host, port=22, user=user, password=password) as m:
        for vlan_id in range(vlan_id_start, vlan_id_end + 1):
            vlan_str = str(vlan_id)
            try:
                disable_vlan_on_trunk_int(m, intf_num, vlan_str)
                remove_vlan(m, vlan_str)
            except operations.rpc.RPCError:
                # Vlan might not be configured.
                pass
        sys.exit(0)
    sys.exit(1)


def print_usage():
    print "Usage:"
    print "    python %s <nexus-ip> <user> <password> " % sys.argv[0]
    print "              <intf-num> <vlan-start> <vlan-end>"
    print "Example:"
    print "    python %s 10.0.1.32 admin MyPassword 1/9 810 813" % sys.argv[0]
    print "Note: VLAN range is inclusive."
    print "Note: Number of VLANs in VLAN range should not exceed 100."


if __name__ == '__main__':
    if "--help" in sys.argv:
        print_usage()
        sys.exit(0)
    if len(sys.argv) != 7:
        print_usage()
        sys.exit(1)
    clear_nexus_config(sys.argv[1], sys.argv[2], sys.argv[3],
                       sys.argv[4], sys.argv[5], sys.argv[6])
