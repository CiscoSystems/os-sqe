#------------------------------------------------------------------
# hyp.sh
# ------------------------------------------------------------------
# July 2016, Puneet Konghot Nair (pkonghot@cisco.com)
# Copyright (c) 2016 by cisco Systems, Inc.
# All rights reserved.
# ------------------------------------------------------------------

date
HYPERVISOR_ARRAY=(`nova hypervisor-list | grep -Evi "Hypervisor" | awk -F"|" '{print $3}' | sed "s/ //g"`)
for HYPERVISOR in "${HYPERVISOR_ARRAY[@]}"
do
    printf "\n##################################################################################################\n"
    nova hypervisor-servers $HYPERVISOR | grep instance
    printf "\nNumber of VMs compute node ${HYPERVISOR} = "
    nova hypervisor-servers $HYPERVISOR | grep instance | wc -l
    printf "\n--------------------------------------------------------------------------------------------------\n"
done
printf "\n"
nova list --field name,status,host 
printf "Total number of active VMs = "
nova list --field name,status,host | grep -E "ACTIVE" | wc -l
nova list | grep -Eiv "ACTIVE" | grep -Eiv "Networks" | grep -Eiv "\----------"
printf "\n"

