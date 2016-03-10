#!/usr/bin/env python
"""
The script deletes following configurations and artifacts in UCSM:
* Delete vlans from all interfaces of service profiles
* Delete port profiles
* Delete vlan profiles
"""

import argparse
import paramiko
import re

client = None

def run(cmd):
    print 'Run command: [%s]' % cmd
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.readlines()

def parse_table(lines):
    data = list()
    if not lines:
        return data
    header_line = lines[2].strip()
    space_holder = re.split('\s+', lines[3].strip())
    tinfo = dict()
    start = 0
    for i in range(0, len(space_holder)):
        end = start + len(space_holder[i]) + 1
        tinfo[header_line[start:end].strip()] = (start, end)
        start = end
    for i in range(4, len(lines)):
        row = dict()
        for name, pos in tinfo.iteritems():
            row[name] = lines[i].strip()[pos[0]:pos[1]]
        data.append(row)
    return data

def parse_detail(lines):
    data = list()
    segment = dict()
    for i in range(2, len(lines)):
        line = lines[i].strip()
        if not line:
            data.append(segment)
            segment = dict()
            continue
        kv = re.split(':', line, maxsplit=1)
        segment[kv[0]] = kv[1]
    if segment not in data:
        data.append(segment)
    return data

def main(ip, username, password, skip_vlans):
    global client
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(ip, username=username, password=password)

    try:
        print "Delete vlans from service profiles"
        service_profiles = parse_table(run('scope org; show service-profile'))
        for service_profile in service_profiles:
            name = service_profile['Service Profile Name']
            scope_sp = 'scope org; scope service-profile %s' % name
            vnics = parse_table(run(scope_sp + '; show vnic'))
            for vnic in vnics:
                scope_vnic = scope_sp + '; scope vnic %s' % vnic['Name']
                eth_ifs = parse_detail(run(scope_vnic + '; show eth-if'))
                for eth_if in eth_ifs:
                    if int(eth_if['VLAN ID']) in skip_vlans:
                        continue
                    print run(scope_vnic + '; delete eth-if %s; commit-buffer' % eth_if['Name'])

        print "Delete port profiles"
        port_profiles = parse_table(run('scope system; scope vm-mgmt; scope profile-set; show port-profile'))
        for port_profile in port_profiles:
            print run('scope system; scope vm-mgmt; scope profile-set; delete port-profile %s; commit-buffer' % port_profile['Name'])

        print "Delete vlan profiles"
        vlans = parse_table(run('scope eth-uplink; show vlan'))
        for vlan in vlans:
            if int(vlan['VLAN ID']) in skip_vlans:
                continue
            print run('scope eth-uplink; delete vlan %s; commit-buffer' % vlan['Name'])

    except Exception as e:
        print e
    client.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--skip-vlans', required=True)
    args = parser.parse_args()

    skip_vlans = [int(vlan) for vlan in args.skip_vlans.split(',')]
    main(args.ip, args.username, args.password, skip_vlans)
