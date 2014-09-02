#!/bin/bash
if [ ! -z "$1" ]; then
    labid=$1
else if [ ! -z "$LAB" ]; then
    labid=$LAB
else
    exit 1
fi
fi

for box in $(virsh list --name --all | grep "${labid}-")
do
    for snap in $(virsh snapshot-list ${box} --name)
    do
        virsh snapshot-delete ${box} ${snap}
    done
    #virsh destroy ${box}
    #virsh undefine ${box}
done
