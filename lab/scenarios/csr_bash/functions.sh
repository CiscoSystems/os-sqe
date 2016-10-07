#------------------------------------------------------------------
# functions.sh
# ------------------------------------------------------------------
# July 2016, Puneet Konghot Nair (pkonghot@cisco.com)
# Copyright (c) 2016 by cisco Systems, Inc.
# All rights reserved.
# ------------------------------------------------------------------

function get_num_vm_on_node {
    local NUM_VM=(`nova hypervisor-servers $1 | grep "instance" | wc -l`)
    # echo "Number of VMs on $1 was $NUM_VM".
    echo $NUM_VM
}

function get_one_vm_on_node {
    local VM_ID=(`nova hypervisor-servers $1 | grep "instance" | awk -F"|" '{print $2}' | sed "s/ //g"`)
    echo ${VM_ID[0]}
}

function get_hypervisor_list {
    local HYPERVISOR_ARRAY=(`nova hypervisor-list | awk -F"|" '{print $3}' | sed "s/ //g"`)
    echo $HYPERVISOR_ARRAY
}

function create_avoidance_hint_from_ids {
    # "$@": all the VMs we should not be running near
    # output: nova boot options to avoid them

    local HYPERVISOR_ARRAY=(`nova hypervisor-list | grep -Eiv "Hypervisor hostname" | awk -F"|" '{print $3}' | sed "s/ //g"`)
    local VM_ID_ARRAY=()
    for HYPERVISOR in "${HYPERVISOR_ARRAY[@]}"
    do
        VM_COUNT=($(get_num_vm_on_node ${HYPERVISOR}))
        #printf "VM_COUNT= ${VM_COUNT}\n"
        if [ ${VM_COUNT} -gt 0 ]
        then
            local VM_ID=($(get_one_vm_on_node $HYPERVISOR))
            #printf "VM_ID=${VM_ID} \n"
            VM_ID_ARRAY+=( ${VM_ID})
        fi
    done
    #printf "VM_ID_ARRAY = ${VM_ID_ARRAY[@]} \n"
    if [ ${#VM_ID_ARRAY[@]} -gt 0 ]
    then
        for f in "${VM_ID_ARRAY[@]}"; do
	    echo --hint different_host="$f"
        done
    fi
}

function create_same_host_hint_from_ids {
    echo --hint same_host="$1"
}
