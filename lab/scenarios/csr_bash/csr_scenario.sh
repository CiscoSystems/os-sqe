#!/bin/bash
#-----------------------------------------------------------------------
# ntt_csr_create.sh -- Creates CSRs attached to 3x virtual networks.
# source openrc
# csr_create.sh [-s]-l <number of CSRs> -f <number of CSR per compute node, 
# default 10> <total time to sleep between successive nova boot 
# commands, default 4 sec>
# -s uses the SameHostFilter.  By default it will use the ServerGroupAffinityFilter.
#-----------------------------------------------------------------------
# July 2016, Puneet Konghot Nair (pkonghot@cisco.com)
# Copyright (c) 2016 by cisco Systems, Inc.
# All rights reserved.
# ------------------------------------------------------------------

opt_same_host=

badopt=


opt_same_host=
opt_create=
opt_first=1
opt_last=
opt_pack=10
opt_delay=4
opt_security=
while getopts 'scef:l:p:d:' arg ; do
    case ${arg} in
    s)
        opt_same_host=1
	;;
    c)
        opt_create=1
	;;
    e)
        opt_security=1
	;;
    f)
	opt_first="$OPTARG"
	;;
    l)
	opt_last="$OPTARG"
	;;
    d)
	opt_delay="$OPTARG"
	;;
    p)
	opt_pack="$OPTARG"
	;;
    ?)
	badargs=1
	;;
    esac
done

usage() {
    cat <<EOF
Usage:
   -s Use SameHostFilter (default: use server affinity groups to fill a host)
   -c Create flavor, networks, image; modify default security group; fix quotas
   -e Set address-pair security
   -f First VM number to run (default 1, must be the first VM on a host)
   -l Last VM number to run
   -d Delay in s between successive VM runs (4s by default; will wait for first
      VMs on host to go active, so these VMs may take longer than this time)
   -p Packing of VMs per host (default 10)
EOF
    exit 1
}

if [ "$badargs" == 1 ] ; then
    usage
elif [ -z "$opt_last" ] ; then
    echo "ERROR: Must give last VM"
    echo
    usage
fi

same_host_filter() {
    [ ! -z "$opt_same_host" ]
}

if [ "$1" == "-s" ]; then
    # Use the samehost filter, not the servergroup affinity filter (which is the default)
    shift
fi

same_host_filter && echo same host set
same_host_filter || echo server affinity set

# At the moment, the differenthostfilter keeps VMs apart.

source functions.sh

# Show what's currently running.
./hyp.sh


if [ ! -z "$opt_create" ] ; then
    # Create OpenStack "flavors".
    nova flavor-create FOR_CSR auto 4096 0 2
    nova flavor-key FOR_CSR set hw:cpu_policy=dedicated hw:mem_page_size=2048 hw:numa_nodes=1

    # Update security groups
    nova secgroup-add-rule default icmp -1 -1 0.0.0.0/0
    nova secgroup-add-rule default tcp 1 65000 0.0.0.0/0
    nova secgroup-add-rule default udp 1 65000 0.0.0.0/0

    # Update quotas
    nova quota-update --cores -1 --ram -1 --instances -1 --server-groups -1 `openstack project show -c id -f value ${OS_TENANT_NAME}`
    neutron quota-update --port -1 --tenant_id `openstack project show -c id -f value ${OS_TENANT_NAME}`

    # Upload image to Glance.
    glance image-create --disk-format qcow2 --container-format bare --name CSR1KV --file csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2

    # Create networks
    neutron net-create vts-net-1
    neutron subnet-create vts-net-1 1111::/64 --ip-version 6 --name vts-subnet-1 --enable_dhcp=False --gateway 1111::1

    neutron net-create vts-net-2
    neutron subnet-create vts-net-2 2.2.0.0/16 --name vts-subnet-2 --enable_dhcp=False --gateway 2.2.0.1

    neutron net-create vts-net-3
    neutron subnet-create vts-net-3 3.3.0.0/16 --name vts-subnet-3 --enable_dhcp=False --gateway 3.3.0.1

    echo "Pause for thought..."
    sleep 10
fi

#-----------------------------------------------------------------------
# Get network IDs of Provider Networks
neutron net-list
NP1=$(neutron net-show -f value -c id vts-net-1)
NP2=$(neutron net-show -f value -c id vts-net-2)
NP3=$(neutron net-show -f value -c id vts-net-3)

#-----------------------------------------------------------------------

vm_active() {
    [ "$(openstack server show -c status -f value $1)" == ACTIVE ]
}

wait_for_active() {
    local f
    echo -n "Waiting for life.."
    for f in `seq 1 60`; do
        local state="$(openstack server show -c status -f value $1)"
        case "$state" in
	ACTIVE)
	    echo " ready."
            openstack server show $1
	    return 0
	    ;;
	ERROR)
	    echo " failed."
            openstack server show $1
	    return 1
	    ;;
	esac
	echo -n .
        sleep 2
    done
    openstack server show $1
    echo " timed out."
    return 1 # VM failed to come up in reasonable time - ~60s
}

#-----------------------------------------------------------------------
# Boot VMs with some day-zero configs

MAX_PER_COMPUTE=${opt_pack}

# TODO should check opt_first is a seed VM
if (( ${opt_first} % ${MAX_PER_COMPUTE} == 1 )) ; then
    true # all good
else
    echo "First VM must be the first VM on a host"
    exit 1
fi

# TODO won't work with big counts
let i=1+${opt_first}
j=0

tmpfile=`mktemp`
for COUNT in `seq ${opt_first} ${opt_last}`; do
    sleep $opt_delay & # bg process; will be waited for later

    VM_NAME=CSR-${COUNT}

    cp cloud-cfg-CSR-base ${tmpfile}
    sleep 2
    sed -i "s/CSR_NAME/${VM_NAME}/g" ${tmpfile}
    sed -i "s/ADDR_G1_V6/1111::${COUNT}/g" ${tmpfile}
    sed -i "s/MASK_G1_V6/64/g" ${tmpfile}
    sed -i "s/ADDR_G2_V4/2.2.${j}.${i}/g" ${tmpfile}
    sed -i "s/MASK_G2_V4/255.255.0.0/g" ${tmpfile}
    sed -i "s/ADDR_G3_V4/3.3.${j}.${i}/g" ${tmpfile}
    sed -i "s/MASK_G3_V4/255.255.0.0/g" ${tmpfile}

    \cp $tmpfile ./cfg/cloud-cfg-CSR-${COUNT}

    # If this is to be the first VM on a new host, this returns true
    seed_vm() {
	(( ${COUNT} % ${MAX_PER_COMPUTE} == 1 ))
    }

    if seed_vm; then
	echo "Starting seed VM on a new host"
	# Reset the same-hostness by whichever filter type is in
	# action - seed VMs are not on the same host as anything.

	if same_host_filter; then
	    SAME_HOST_HINT='' # Same-host: no requirements for seed VM
	else
	    # server group: all VMs, seed included, must use the same server group; make a new group
            let COMP_NUM=(${COUNT}/${MAX_PER_COMPUTE})+1
            nova server-group-create server-group-${COMP_NUM} affinity
            LIST_ID=(`nova server-group-list | grep "server-group-${COMP_NUM} " | awk -F"|" '{print $2}' | sed "s/ //g"`)
	    SAME_HOST_HINT="--hint group=${LIST_ID}"
        fi

        # -pkn This logic does not work in testbeds with mixed types of compute
        # nodes whne script is run to kill/respin Vms. Seed ID list
        # should be dynamilcally learnt from the compute hosts. 
	#DIFFERENT_HOST_HINT="`create_avoidance_hint_from_ids $seed_ids`"
	DIFFERENT_HOST_HINT="`create_avoidance_hint_from_ids`"

    else
	echo "Starting VM co-located with last seed VM"
	if same_host_filter; then
	    SAME_HOST_HINT=`create_same_host_hint_from_ids $last_seed_vm`
	else
	    # We use the server group affinity filter - this is the same hint as the previous VM
	    true
	fi
	# The server group affinity is set *before* the seed VM is run and applied to all in the group

	# The different host filter should only be applied to the seed VM and none of the others
	DIFFERENT_HOST_HINT=
    fi

    echo "Keeping on same host using: SAME_HOST_HINT=${SAME_HOST_HINT}"
    echo "Avoiding VMs using: DIFFERENT_HOST_HINT=${DIFFERENT_HOST_HINT}"

    show_and_run() {
	echo "`date`: $@" 1>&2
	"$@"
    }
    # Runs VM; saves ID to vm_id
    show_and_run nova boot --image CSR1KV --flavor FOR_CSR --nic net-id=${NP1} --nic net-id=${NP2} --nic net-id=${NP3} \
	    --config-drive=true --file iosxe_config.txt=${tmpfile} \
	    ${SAME_HOST_HINT} ${DIFFERENT_HOST_HINT} ${VM_NAME}
    vm_id=(`nova list | grep "${VM_NAME} " | awk -F"|" '{print $2}' | sed "s/ //g"`)

    if [ -z "$vm_id" ] ; then
	echo "ERROR: VM ${VM_NAME} failed to run"
	exit 1
    fi

    if seed_vm; then
        # Wait for this VM to come up - placement will fail with seed VMs in limbo
	if wait_for_active $vm_id; then 
	    :
	else
	    echo "ERROR: Seed VM failed to activate - cannot place remaining VMs"
	    exit 1
	fi

	# This is a seed VM; add it to the seed list so that other seed VMs avoid it
        # -pkn This logic breaks in repeated runs of the script. Seed ID list
        # should be dynamilcally learnt from the compute hosts. 
	last_seed_vm=${vm_id}
        seed_ids="$seed_ids $vm_id"
    fi

    echo "Started CSR #${COUNT} with ID: $vm_id ..."
    echo

    # Work out our next IP address components
    let i=i+1
    if [ ${i} -eq 254 ]; then
        let i=1
        let j=j+1
    fi

    let COUNT=COUNT+1
    wait # (for the sleep at the start of the loop to exit)
done

rm ${tmpfile}

#-----------------------------------------------------------------------
if [ "$opt_security" ] ; then 
    # Disable anti-spoofing rules on all neutron ports.
    for PORT in $(neutron port-list -c ID -f value)
    do
	neutron port-update ${PORT} --allowed-address-pairs type=dict list=true ip_address=0.0.0.0/0
    done
fi

#-----------------------------------------------------------------------
./hyp.sh

