#!/bin/bash

source ./backup_config

if [ ! -z "$1" ]; then
    DATE=$1
    curdir=${BU_DIR}/$DATE
    if [ ! -d "${curdir}" ]; then
        echo "Directory "${curdir}" doesn't exist!"
        exit 1
    fi
else
    DATE=$(ls $BU_DIR | grep -Eo "^[0-9]+$" | sort -n | tail -1)
    curdir=${BU_DIR}/$DATE
fi

if [ -z "$curdir" ];
then
    echo "Not found directory!"
    exit 1
fi

function redefine_jenkins {
    # redefine everything locally
    NEW_NAME=${JENKINS_VM_NAME}_${DATE}
    cp $curdir/${JENKINS_VM_NAME}.xml $curdir/${NEW_NAME}.xml
    sed -i "s@<name>${JENKINS_VM_NAME}</name>@<name>${NEW_NAME}</name>@" $curdir/${NEW_NAME}.xml
    sed -i "s@/opt/qa/jenkins_disk.qcow2@${curdir}/jenkins_disk.qcow2@" $curdir/${NEW_NAME}.xml
    echo "Define Jenkins machine"
    virsh -c $LOCAL_URL define $curdir/${NEW_NAME}.xml
    # redefine snapshots
    echo "Redefine Jenkins snapshots"
    for i in $(ls $curdir/jenkinsnap/*.xml);
    do
        sed -i "s@<name>${JENKINS_VM_NAME}</name>@<name>${NEW_NAME}</name>@" $i
        sed -i "s@/opt/qa/jenkins_disk.qcow2@${curdir}/jenkins_disk.qcow2@" $i
        virsh -c $LOCAL_URL snapshot-create ${NEW_NAME} $i --redefine
    done
}

function redefine_zuul {
     # redefine everything locally
    NEW_NAME=${ZUUL_VM_NAME}_${DATE}
    cp $curdir/${ZUUL_VM_NAME}.xml $curdir/${NEW_NAME}.xml
    sed -i "s@<name>${ZUUL_VM_NAME}</name>@<name>${NEW_NAME}</name>@" $curdir/${NEW_NAME}.xml
    sed -i "s@/opt/qa/zuul.@${curdir}/zuul.@" $curdir/${NEW_NAME}.xml
    echo "Define Zuul machine"
    virsh -c $LOCAL_URL define $curdir/${NEW_NAME}.xml
    # redefine snapshots
    echo "Redefine Zuul snapshots"
    for i in $(ls $curdir/zuulsnap/*.xml);
    do
        sed -i "s@<name>${ZUUL_VM_NAME}</name>@<name>${NEW_NAME}</name>@" $i
        sed -i "s@/opt/qa/zuul.@${curdir}/zuul.@" $i
        virsh -c $LOCAL_URL snapshot-create ${NEW_NAME} $i --redefine
    done

}

function delete_old () {
    target=$1
    old=$(virsh -c $LOCAL_URL list --all | grep -Eo "${target}_[0-9]+")
    for vm in $old
        do
        for i in `virsh -c $LOCAL_URL snapshot-list ${vm} | awk {'print $1'} | sed -n '/[a-Z]/p' | grep -v Name`;
            do
                virsh -c $LOCAL_URL snapshot-delete ${vm} $i
            done
        done
        virsh -c $LOCAL_URL destroy ${vm}
        virsh -c $LOCAL_URL undefine ${vm}
}



delete_old ${ZUUL_VM_NAME}
delete_old ${JENKINS_VM_NAME}
redefine_jenkins
redefine_zuul