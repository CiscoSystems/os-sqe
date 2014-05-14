#!/bin/bash
source variables.sh

rand_mac(){
  echo $(openssl rand -hex 6 | sed 's/\(..\)/\1:/g; s/.$//')
}
j=2
build_server_mac=$(rand_mac)
control_servers_macs=()
compute_servers_macs=()
dhcp_records="<host mac=\"${build_server_mac}\" name=\"build-server.domain.name\" ip=\"${NET_BOOT}.${j}\" />"
for ((i = 0; i < $CONTROL_SERVERS; i++)); do
  j=$(($j+1))
  name="$(printf "control-server%02d" $i).domain.name"
  control_servers_macs+=($(rand_mac))
  dhcp_records="${dhcp_records}<host mac=\"${control_servers_macs[$i]}\" name=\"${name}\" ip=\"${NET_BOOT}.${j}\" />"
done
for ((i = 0; i < $COMPUTE_SERVERS; i++)); do
  j=$(($j+1))
  name="$(printf "compute-server%02d" $i).domain.name"
  compute_servers_macs+=($(rand_mac))
  dhcp_records="${dhcp_records}<host mac=\"${compute_servers_macs[$i]}\" name=\"${name}\" ip=\"${NET_BOOT}.${j}\" />"
done

cat > ${NET_BOOT_XML} <<EOF
<network>
  <name>${NET_BOOT_NAME}</name>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <domain name='domain.name'/>
  <ip address='${NET_BOOT}.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='${NET_BOOT}.2' end='${NET_BOOT}.254' />
      ${dhcp_records}
    </dhcp>
  </ip>
</network>
EOF

cat > ${NET_ADMIN_XML} <<EOF
<network>
  <name>${NET_ADMIN_NAME}</name>
  <domain name='domain.name'/>
  <dns>
    <host ip='${NET_ADMIN}.2'>
      <hostname>build-server</hostname>
      <hostname>build-server.domain.name</hostname>
    </host>
  </dns>
  <ip address='${NET_ADMIN}.1' netmask='255.255.255.0'>
  </ip>
</network>
EOF

cat > ${NET_PUBLIC_XML} <<EOF
<network>
  <name>${NET_PUBLIC_NAME}</name>
  <domain name='domain.name'/>
  <ip address='${NET_PUBLIC}.1' netmask='255.255.255.0'>
  </ip>
</network>
EOF

cat > ${NET_INTERNAL_XML} <<EOF
<network>
  <name>${NET_INTERNAL_NAME}</name>
  <domain name='domain.name'/>
  <ip address='${NET_INTERNAL}.1' netmask='255.255.255.0'>
  </ip>
</network>
EOF

cat > ${NET_EXTERNAL_XML} <<EOF
<network>
  <name>${NET_EXTERNAL_NAME}</name>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <domain name='domain.name'/>
  <ip address='${NET_EXTERNAL}.1' netmask='255.255.255.0'>
  </ip>
</network>
EOF

net_create(){
	name=$1
	file=$2
	virsh net-define ${file}
	virsh net-autostart ${name}
	virsh net-start ${name}
}

net_create ${NET_BOOT_NAME} ${NET_BOOT_XML}
net_create ${NET_ADMIN_NAME} ${NET_ADMIN_XML}
net_create ${NET_PUBLIC_NAME} ${NET_PUBLIC_XML}
net_create ${NET_INTERNAL_NAME} ${NET_INTERNAL_XML}
net_create ${NET_EXTERNAL_NAME} ${NET_EXTERNAL_XML}

# Convert cloud image
echo "Uncompressing cloud image ..."
qemu-img convert -O qcow2 ${IMG_FULLPATH} ${IMG_UNCOMPRESSED_PATH}

main_disk_create(){
    output_file=$1
    size=$2
    qemu-img create -f qcow2 -b ${IMG_UNCOMPRESSED_PATH} ${output_file} ${size}G
}

vm_create(){
	vm_xml=$1
	virsh define ${vm_xml}
}

cat > ${VM_BUILD_XML} <<EOF
<domain type='kvm'>
  <name>${VM_BUILD_NAME}</name>
  <memory unit='KiB'>$((BUILD_SERVER_RAM*GB))</memory>
  <currentMemory unit='KiB'>$((BUILD_SERVER_RAM*GB))</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <os>
    <type arch='x86_64'>hvm</type>
    <boot dev='hd'/>
    <boot dev='cdrom'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <pae/>
  </features>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <pm>
    <suspend-to-mem enabled='no'/>
    <suspend-to-disk enabled='no'/>
  </pm>
  <devices>
  <emulator>/usr/bin/kvm</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='${IMAGES_PATH}/${VM_BUILD_DISK_NAME}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <disk type='file' device='disk'>
      <driver name='qemu' type='raw'/>
      <source file='${IMAGES_PATH}/${VM_BUILD_SEED_IMG}'/>
      <target dev='hda' bus='ide'/>
    </disk>
    <interface type='network'>
      <source network='${NET_BOOT_NAME}'/>
      <mac address='${build_server_mac}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_ADMIN_NAME}'/>
    </interface>
    <input type='mouse' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes'/>
  </devices>
</domain>
EOF
main_disk_create ${IMAGES_PATH}/${VM_BUILD_DISK_NAME} ${BUILD_SERVER_DISK_SIZE}
cloud-localds ${IMAGES_PATH}/${VM_BUILD_SEED_IMG} user-data.yaml
vm_create ${VM_BUILD_XML}

for ((i = 0; i < ${CONTROL_SERVERS}; i++)); do
	name=${VM_CONTROL_NAMES[$i]
	mac=${control_servers_macs[$i]}
	xml=${TEMP_FOLDER}/${name}.xml
	disk=${name}.qcow2
	seed_disk=${name}-seed.qcow2
	
	cat > ${xml} <<EOF
<domain type='kvm'>
  <name>${name}</name>
  <memory unit='KiB'>$((CONTROL_SERVER_RAM*GB))</memory>
  <currentMemory unit='KiB'>$((CONTROL_SERVER_RAM*GB))</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <os>
    <type arch='x86_64' machine='pc-i440fx-1.5'>hvm</type>
    <boot dev='hd'/>
    <boot dev='cdrom'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <pae/>
  </features>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <pm>
    <suspend-to-mem enabled='no'/>
    <suspend-to-disk enabled='no'/>
  </pm>
  <devices>
    <emulator>/usr/bin/kvm</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='${IMAGES_PATH}/${disk}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <disk type='file' device='disk'>
      <driver name='qemu' type='raw'/>
      <source file='${IMAGES_PATH}/${seed_disk}'/>
      <target dev='hda' bus='ide'/>
    </disk>
    <interface type='network'>
      <source network='${NET_BOOT_NAME}'/>
      <mac address='${mac}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_ADMIN_NAME}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_PUBLIC_NAME}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_INTERNAL_NAME}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_EXTERNAL_NAME}'/>
    </interface>
    <input type='mouse' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes'/>
  </devices>
</domain>
EOF
    main_disk_create ${IMAGES_PATH}/${disk} ${CONTROL_SERVER_DISK_SIZE}
    cloud-localds ${IMAGES_PATH}/${seed_disk} user-data.yaml
	vm_create ${xml}
done

for ((i = 0; i < $COMPUTE_SERVERS; i++)); do
    name=${VM_COMPUTE_NAMES[$i]}
    mac=${compute_servers_macs[$i]}
    xml=${TEMP_FOLDER}/${name}.xml
    disk=${name}.qcow2
    seed_disk=${name}-seed.qcow2

    cat > ${xml} <<EOF
<domain type='kvm'>
  <name>${name}</name>
  <memory unit='KiB'>$((COMPUTE_SERVER_RAM*GB))</memory>
  <currentMemory unit='KiB'>$((COMPUTE_SERVER_RAM*GB))</currentMemory>
  <vcpu placement='static'>${COMPUTE_SERVER_CPU}</vcpu>
  <os>
    <type arch='x86_64' machine='pc-i440fx-1.5'>hvm</type>
    <boot dev='hd'/>
    <boot dev='cdrom'/>
  </os>
  <features>
    <acpi/>
    <apic/>
    <pae/>
  </features>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <pm>
    <suspend-to-mem enabled='no'/>
    <suspend-to-disk enabled='no'/>
  </pm>
  <devices>
    <emulator>/usr/bin/kvm</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='${IMAGES_PATH}/${disk}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <disk type='file' device='disk'>
      <driver name='qemu' type='raw'/>
      <source file='${IMAGES_PATH}/${seed_disk}'/>
      <target dev='hda' bus='ide'/>
    </disk>
    <interface type='network'>
      <source network='${NET_BOOT_NAME}'/>
      <mac address='${mac}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_ADMIN_NAME}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_PUBLIC_NAME}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_INTERNAL_NAME}'/>
    </interface>
    <interface type='network'>
      <source network='${NET_EXTERNAL_NAME}'/>
    </interface>
    <input type='mouse' bus='ps2'/>
    <graphics type='vnc' port='-1' autoport='yes'/>
  </devices>
</domain>
EOF
    main_disk_create ${IMAGES_PATH}/${disk} ${COMPUTE_SERVER_DISK_SIZE}
    cloud-localds ${IMAGES_PATH}/${seed_disk} user-data.yaml
    vm_create ${xml}
done
