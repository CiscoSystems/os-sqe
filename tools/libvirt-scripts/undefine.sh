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
	domstate=$(virsh domstate $name)
	if [[ "$domstate" == "running" ]] ; then
		virsh destroy $name
	fi
	virsh undefine $name
	rm ${IMAGES_PATH}/${disk}
}

net_undefine ${NET_BOOT_NAME}
net_undefine ${NET_ADMIN_NAME}
net_undefine ${NET_PUBLIC_NAME}
net_undefine ${NET_INTERNAL_NAME}
net_undefine ${NET_EXTERNAL_NAME}

vm_undefine ${VM_BUILD_NAME} ${VM_BUILD_DISK_NAME}
rm ${IMAGES_PATH}/${VM_BUILD_SEED_IMG}

for name in ${VM_CONTROL_NAMES[@]}; do
	vm_undefine ${name} ${name}.qcow2
	rm ${IMAGES_PATH}/${name}-seed.qcow2
done
for name in ${VM_COMPUTE_NAMES[@]}; do
    vm_undefine ${name} ${name}.qcow2
    rm ${IMAGES_PATH}/${name}-seed.qcow2
done

rm ${IMG_UNCOMPRESSED_PATH}
