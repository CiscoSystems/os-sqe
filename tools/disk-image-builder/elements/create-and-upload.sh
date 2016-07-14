#!/usr/bin/env bash

export ELEMENTS_PATH=$(pwd)

workspace=$(mktemp -d)
cd ${workspace}

image_name=fedora-dnsmasq-localadmin-ubuntu.qcow2

git clone https://git.openstack.org/openstack/diskimage-builder
virtualenv venv
source venv/bin/activate

pip install -e ./diskimage-builder
disk-image-create fedora vm selinux-permissive dnsmasq users ip-addresses -a amd64 -o ${image_name}
deactivate

cat >${image_name}.sha256sum.txt<<EOF
$(sha256sum ${image_name})
EOF

cd -
rm -rf ${workspace}
