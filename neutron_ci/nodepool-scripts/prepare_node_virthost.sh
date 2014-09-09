#!/bin/bash

WORK_DIR=`pwd`

bash ./prepare_jenkins_node.sh

sudo apt-get install -y qemu-kvm libvirt-bin ubuntu-vm-builder bridge-utils cloud-utils