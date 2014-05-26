#!/bin/bash
source variables.sh

rand_mac(){
  echo $(od -An -N6 -tx1 /dev/urandom | sed -e 's/^  *//' -e 's/  */:/g' -e 's/:$//' -e 's/^\(.\)[13579bdf]/\10/')
}
j=2
build_server_mac=$(rand_mac)
build_server_ip=${NET_BOOT}.${j}
control_servers_macs=()
control_servers_ips=()
compute_servers_macs=()
compute_servers_ips=()
dhcp_records="<host mac=\"${build_server_mac}\" name=\"build-server.domain.name\" ip=\"${build_server_ip}\" />"
for ((i = 0; i < $CONTROL_SERVERS; i++)); do
  j=$(($j+1))
  name="$(printf "control-server%02d" $i).domain.name"
  control_servers_macs+=($(rand_mac))
  control_servers_ips+=(${NET_BOOT}.${j})
  dhcp_records="${dhcp_records}<host mac=\"${control_servers_macs[$i]}\" name=\"${name}\" ip=\"${control_servers_ips[$i]}\" />"
done
for ((i = 0; i < $COMPUTE_SERVERS; i++)); do
  j=$(($j+1))
  name="$(printf "compute-server%02d" $i).domain.name"
  compute_servers_macs+=($(rand_mac))
  compute_servers_ips+=(${NET_BOOT}.${j})
  dhcp_records="${dhcp_records}<host mac=\"${compute_servers_macs[$i]}\" name=\"${name}\" ip=\"${compute_servers_ips[$i]}\" />"
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

if [ "${BOOT_TYPE}" == "net" ]; then
    # create storage pool if it does not exist
    virsh pool-uuid ${STORAGE_POOL} &>/dev/null
    if (( $? )); then
        cat > ${STORAGE_POOL_XML}<<EOF
<pool type="dir">
    <name>${STORAGE_POOL}</name>
    <target>
        <path>${IMAGES_PATH}</path>
    </target>
</pool>
EOF
        virsh pool-create --file ${STORAGE_POOL_XML}
    fi
fi

# Convert cloud image
echo "Uncompressing cloud image ..."
qemu-img convert -O qcow2 ${IMG_FULLPATH} ${IMG_UNCOMPRESSED_PATH}

main_disk_create(){
    name=$1
    size=$2
    type=$3
    output_file=${IMAGES_PATH}/${name}.qcow2

    if [ "${type}" == "net" ]; then
        vol_xml=${TEMP_FOLDER}/${name}-vol.xml
        cat >${vol_xml}<<EOF
<volume>
<name>${name}.qcow2</name>
<allocation>$((size*GB_bytes))</allocation>
<capacity>$((size*GB_bytes))</capacity>
<target>
  <path>${output_file}</path>
</target>
</volume>
EOF
        virsh vol-create --pool ${STORAGE_POOL} --file ${vol_xml}
        cat <<EOF
<disk type='file' device='disk'>
  <driver name='qemu' type='qcow2'/>
  <source file='${output_file}'/>
  <target dev='vda' bus='virtio'/>
</disk>
EOF
    elif [ "${type}" == "cloudimg" ]; then
        seed_disk=${IMAGES_PATH}/${name}-seed.img
        qemu-img create -f qcow2 -b ${IMG_UNCOMPRESSED_PATH} ${output_file} ${size}G
        cloud-localds ${seed_disk} user-data.yaml
        cat <<EOF
<disk type='file' device='disk'>
  <driver name='qemu' type='qcow2'/>
  <source file='${output_file}'/>
  <target dev='vda' bus='virtio'/>
</disk>
<disk type='file' device='disk'>
  <driver name='qemu' type='raw'/>
  <source file='${seed_disk}'/>
  <target dev='hda' bus='ide'/>
</disk>
EOF
    fi
}

vm_create(){
	vm_xml=$1
	virsh define ${vm_xml}
}

disk=$(main_disk_create ${VM_BUILD_DISK_NAME} ${BUILD_SERVER_DISK_SIZE} "cloudimg")
cat > ${VM_BUILD_XML} <<EOF
<domain type='kvm'>
  <name>${VM_BUILD_NAME}</name>
  <memory unit='KiB'>$((BUILD_SERVER_RAM*GB))</memory>
  <currentMemory unit='KiB'>$((BUILD_SERVER_RAM*GB))</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <os>
    <type arch='x86_64'>hvm</type>
    <boot dev='hd'/>
    <boot dev='network'/>
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
    ${disk}
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
vm_create ${VM_BUILD_XML}
echo "Build server ip: ${build_server_ip}"; echo

for ((i = 0; i < ${CONTROL_SERVERS}; i++)); do
	name=${VM_CONTROL_NAMES[$i]}
	mac=${control_servers_macs[$i]}
	xml=${TEMP_FOLDER}/${name}.xml
	disk=$(main_disk_create ${name} ${CONTROL_SERVER_DISK_SIZE} ${BOOT_TYPE})
	
	cat > ${xml} <<EOF
<domain type='kvm'>
  <name>${name}</name>
  <memory unit='KiB'>$((CONTROL_SERVER_RAM*GB))</memory>
  <currentMemory unit='KiB'>$((CONTROL_SERVER_RAM*GB))</currentMemory>
  <vcpu placement='static'>1</vcpu>
  <os>
    <type arch='x86_64' machine='pc-i440fx-1.5'>hvm</type>
    <boot dev='hd'/>
    <boot dev='network'/>
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
    ${disk}
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
    vm_create ${xml}
    echo "Control server IP: ${control_servers_ips[$i]}"; echo
done

for ((i = 0; i < $COMPUTE_SERVERS; i++)); do
    name=${VM_COMPUTE_NAMES[$i]}
    mac=${compute_servers_macs[$i]}
    xml=${TEMP_FOLDER}/${name}.xml
    disk=$(main_disk_create ${name} ${COMPUTE_SERVER_DISK_SIZE} ${BOOT_TYPE})
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
    <boot dev='network'/>
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
    ${disk}
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
    vm_create ${xml}
    echo "Compute server IP: ${compute_servers_ips[$i]}"; echo
done
