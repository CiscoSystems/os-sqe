import os
import paramiko
import sys

nexus_ip = os.environ.get('NEXUS_IP')
nexus_user = os.environ.get('NEXUS_USER')
nexus_password = os.environ.get('NEXUS_PASSWORD')
nexus_intf_num = os.environ.get('NEXUS_INTF_NUM')
nexus_vlan_start = os.environ.get('NEXUS_VLAN_START')
nexus_vlan_end = os.environ.get('NEXUS_VLAN_END')


def clear_nexus_config(ip, user, password, intf_num, vlan_start, vlan_end):
    client = paramiko.client.SSHClient()
    client.load_system_host_keys()

    for vlan in range(int(vlan_start), int(vlan_end) + 1):
        client.connect(ip, username=user, password=password)

        cmd = 'config terminal ; ' \
              'interface Ethernet {0} ; ' \
              'switchport trunk allowed vlan remove {1} ;'.format(intf_num, vlan)
        print cmd
        stdin, stdout, stderr = client.exec_command(cmd)
        print stdout.readlines()

        cmd = 'config terminal ; no vlan {0} ;'.format(vlan)
        print cmd
        stdin, stdout, stderr = client.exec_command(cmd)
        print stdout.readlines()

        client.close()

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
