#!/bin/bash
if [ ! -z "$1" ]; then
    labid=$1
else if [ ! -z "$LAB" ]; then
    labid=$LAB
else
    exit 1
fi
fi

for pool in $(virsh pool-list --all | grep "\-${labid} " | awk {'print $1'});
do
    virsh pool-start $pool || :
done
for vm in $(virsh list --name --all | grep "${labid}-");
do
    virsh snapshot-revert $vm original || :
done
for net in $(virsh net-list --all | grep "${labid}-" | awk {'print $1'});
do
    virsh net-start $net || :
done
