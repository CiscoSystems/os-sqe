#!/usr/bin/env bash
# Converts bridge and bond (plugged into bridge) into OVSBridge and OVSBond
#
# Ex:
# Call it on the management node:
#       bash ovs-convert-bridge-bond.sh br_mgmt
#
# Result:
# [root@mgmt ~]# ovs-vsctl show
# d6082520-67f8-4dab-b830-9e400b212bca
#     Bridge br_mgmt
#         Port br_mgmt
#             Interface br_mgmt
#                 type: internal
#         Port "bond0"
#             Interface "enp6s0"
#             Interface "enp7s0"
#     ovs_version: "2.4.0"


bridge_name=$1

help="bash <script_location> <bridge_name>"
if [ -z $bridge_name ]; then
    echo "Bridge name is not specified. Ex: $help"
    exit 1
fi
if ! ( ip address show ${bridge_name} ); then
    echo "Could not find bridge ${bridge_name}"
    exit 1
fi

bond_name=$(ip link | awk -F '( |:)' "/noqueue master ${bridge_name}/"'{print $3}')
if [ -z $bond_name ]; then
    echo "Bond is not found."
    exit 1
fi

# install and enable OpenVSwitch
if ! ( yum install -y openvswitch && systemctl enable openvswitch && systemctl start openvswitch ); then
    echo "Could not install OpenVSwitch"
    exit 1
fi

net_scripts_path="/etc/sysconfig/network-scripts"

# Create backup
cp -r $net_scripts_path ./network-scripts_backup

# List of slave interface. Populated in loop below. Used in bond config.
bond_ifaces=""

# Update slave interfaces of the bond
for int in $(ip link show | grep "master ${bond_name}" | awk -F '( |:)' '{print $3}'); do
    ifcfg_int_file="${net_scripts_path}/ifcfg-${int}"
    sed -i '/MASTER=/d' $ifcfg_int_file
    sed -i '/SLAVE=/d' $ifcfg_int_file
    bond_ifaces="${bond_ifaces} ${int}"
done

# Update bond. Turn it into OVS Bond
ifcfg_bond_file="${net_scripts_path}/ifcfg-${bond_name}"
sed -i '/BONDING_MASTER=/d' $ifcfg_bond_file
sed -i '/BONDING_OPTS=/d' $ifcfg_bond_file
sed -i 's/TYPE=.*$/TYPE=OVSBond/' $ifcfg_bond_file
sed -i "s/BRIDGE=.*$/OVS_BRIDGE=${bridge_name}/" $ifcfg_bond_file
grep -q 'DEVICETYPE=' $ifcfg_bond_file && sed -i 's/DEVICETYPE=.*$/DEVICETYPE=ovs/' $ifcfg_bond_file || sed -i "$ a\DEVICETYPE=ovs" $ifcfg_bond_file
grep -q 'BOND_IFACES=' $ifcfg_bond_file && sed -i "s/BOND_IFACES=.*$/BOND_IFACES=\"${bond_ifaces}\"/" $ifcfg_bond_file || sed -i "$ a\BOND_IFACES=\"${bond_ifaces}\"" $ifcfg_bond_file
grep -q 'OVS_OPTIONS=' $ifcfg_bond_file && sed -i 's/OVS_OPTIONS=.*$/OVS_OPTIONS="bond_mode=balance-tcp lacp=active"/' $ifcfg_bond_file || sed -i '$ a\OVS_OPTIONS="bond_mode=balance-tcp lacp=active"' $ifcfg_bond_file

# Update bridge. Turn it into OVS bridge
ifcfg_bridge_file="${net_scripts_path}/ifcfg-${bridge_name}"
sed -i 's/TYPE=.*$/TYPE=OVSBridge/' $ifcfg_bridge_file
grep -q 'DEVICETYPE=' $ifcfg_bridge_file && sed -i 's/DEVICETYPE=.*$/DEVICETYPE=ovs/' $ifcfg_bridge_file || sed -i "$ a\DEVICETYPE=ovs" $ifcfg_bridge_file

ifdown $bridge_name
ifdown $bond_name
systemctl restart network

sysctl -w net.ipv4.ip_forward=1
