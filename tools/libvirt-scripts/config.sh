#!/bin/bash
NAME=lab

# Boot type:
#   cloudimg    - machines will boot from IMG_FULLPATH cloud image
#   net         - all machines exceot build-server will boot over PXE
BOOT_TYPE=cloudimg

# all nets have CIDR=/24, 
# specify first three octets of IPs
NET_BOOT=192.168.0
NET_ADMIN=192.168.1
NET_PUBLIC=192.168.2
NET_INTERNAL=192.168.3
NET_EXTERNAL=10.0.0

BUILD_SERVER_DISK_SIZE=10
BUILD_SERVER_RAM=2

CONTROL_SERVERS=1
CONTROL_SERVER_DISK_SIZE=20
CONTROL_SERVER_RAM=4

COMPUTE_SERVERS=0
COMPUTE_SERVER_DISK_SIZE=20
COMPUTE_SERVER_RAM=4
COMPUTE_SERVER_CPU=1

IMG_FULLPATH=/root/trusty-server-cloudimg-amd64-disk1.img
