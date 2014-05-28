#!/bin/bash
source variables.sh

net_undefine(){
	name=$1
	virsh net-destroy $name
	virsh net-undefine $name
}

vm_undefine(){
	name=$1
    disk=$2
    type=$3
	domstate=$(virsh domstate $name)
	if [[ "$domstate" == "running" ]] ; then
		virsh destroy $name
	fi
	virsh undefine $name
	if [ "${type}" == "net" ]; then
	    virsh vol-delete ${disk} --pool ${STORAGE_POOL}
	elif [ "${type}" == "cloudimg" ]; then
	    rm ${IMAGES_PATH}/${disk}
	    rm ${IMAGES_PATH}/${name}-seed.img
	fi
}

net_undefine ${NET_BOOT_NAME}
net_undefine ${NET_ADMIN_NAME}
net_undefine ${NET_PUBLIC_NAME}
net_undefine ${NET_INTERNAL_NAME}
net_undefine ${NET_EXTERNAL_NAME}

vm_undefine ${VM_BUILD_NAME} ${VM_BUILD_DISK_NAME}.qcow2 "cloudimg"

for name in ${VM_CONTROL_NAMES[@]}; do
	vm_undefine ${name} ${name}.qcow2 ${BOOT_TYPE}
done
for name in ${VM_COMPUTE_NAMES[@]}; do
    vm_undefine ${name} ${name}.qcow2 ${BOOT_TYPE}
done

rm ${IMG_UNCOMPRESSED_PATH}
