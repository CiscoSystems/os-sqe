#!/bin/bash
if [ ! -z "$1" ]; then
    labid=$1
else if [ ! -z "$LAB" ]; then
    labid=$LAB
else
    exit 1
fi
fi

for box in $(virsh list --name | grep "${labid}-")
do
    virsh snapshot-create-as ${box} original
    virsh shutdown ${box}
done
