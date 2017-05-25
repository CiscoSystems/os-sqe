#!/usr/bin/env bash

sudo apt-get install -y git qemu-utils sudo curl kpartx python-setuptools python-dev

image_name=os-sqe-localadmin-ubuntu.qcow2
export ELEMENTS_PATH=$(pwd)/elements

workspace=$(mktemp -d)
cd ${workspace}

git clone https://git.openstack.org/openstack/diskimage-builder

virtualenv venv
source venv/bin/activate
easy_install pip
pip install pytz pep8
pip install -e ./diskimage-builder

disk-image-create fedora vm selinux-permissive dnsmasq iperf users ip-addresses manage-cloud-init -a amd64 -o ${image_name}

deactivate

cat >${image_name}.txt<<EOF
$(md5sum ${image_name}) admin cisco123
EOF
