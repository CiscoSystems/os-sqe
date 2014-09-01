#!/bin/bash
if [ -n "$1" ]; then
    labid=$1
else if [ -n "$LAB" ]; then
    labid=$LAB
else
    echo "No \$LAB variable id defined"
    exit 1
fi
fi

if [ -n "$WORKSPACE" ]; then
    this_=$(readlink -f $0)
    this_dir=$(dirname $this_)
    export WORKSPACE="${this_dir}/../../.."
fi

export DEV_IP=$(sed -n "/${labid}:/{n;p;n;p;}" tools/cloud/cloud-templates/lab.yaml | sed 'N;s/\n/ /' | sed "s/    ip_start: /./g" | sed "s/   net_start: //g")
scp root@${DEV_IP}:/root/openrc ${WORKSPACE}/openrc && cp ${WORKSPACE}/openrc ${WORKSPACE}/openstack-sqe/openrc
