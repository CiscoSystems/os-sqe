#!/bin/bash

source ./backup_config
echo "Start the ball rolling......."

function run() {
  $*
  if [ $? -ne 0 ]
  then
    echo "$* failed with exit code $?"
    return 1
  else
    return 0
  fi
}


function update_time {
    /etc/init.d/ntp stop;
    /usr/sbin/ntpdate ntp.esl.cisco.com || /usr/sbin/ntpdate ntp.ubuntu.com || /usr/sbin/ntpdate 10.81.254.131 || /usr/sbin/ntpdate 10.81.254.202;
    /etc/init.d/ntp start;
}

function mailall {
    nc $mail_srv_ip 25 << EOF
ehlo mail.script
mail from:<backup-server-mosqa@cisco.com>
rcpt to:<$MAILTO>
data
subject: Fail with backups!
$1
.
quit
EOF
}


function mailgood {
    nc $mail_srv_ip 25 << EOF
ehlo mail.script
mail from:<backup-server-mosqa@cisco.com>
rcpt to:<$MAILTO>
data
subject: Backups were created successfully!
$1
.
quit
EOF
}

function prepare_dir () {
    curdir="${BU_DIR}/$1"
    if [ -e $curdir ]
    then
        rm -rf $curdir/*
    fi
    mkdir -p $curdir
    mkdir -p $curdir/jenkinsnap
    mkdir -p $curdir/zuulsnap
    mkdir -p $curdir/jobs
}

function copy_jenkins_home {
    filepath=$curdir"/jenkinshome_${DATE}.tar.gz"
    echo "Copying Jenkins home directory to $filepath"
    ssh  root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} tar -cpzf - ${JENKINS_HOME}" > $filepath
    echo "Finished! File size is $(du -h $filepath | awk {'print $1'})"
}


function copy_jenkins_jobs {
    echo "Started copying jobs"
    jobs=$(ssh root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} ls /var/lib/jenkins/jobs/")
    for job in $jobs; do
        scp -Cqp -o "ProxyCommand ssh -q root@${JENKINS_GATE} nc ${JENKINS_LOCAL_IP} 22"  \
        root@${JENKINS_LOCAL_IP}:/var/lib/jenkins/jobs/${job}/config.xml $curdir/jobs/${job}.xml
    done
    echo "Finished copying jobs"
}

function backup_jenkins {

    # stop jenkins
    stop="java -jar ${JENKINS_CLI}/jenkins-cli.jar -s  http://${JENKINS_LOCAL_IP}:8080/ safe-shutdown --username backup --password Cisco123"
    echo "Stopping Jenkins gracefully"
    ssh  root@${JENKINS_GATE} "$stop"
    sleep 30
    jenkins_status=$(ssh  root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} /etc/init.d/jenkins status" 2>/dev/null)
    start_time=$(date +%s)
    echo "Checking Jenkins status: ${jenkins_status}"
    while [[ $jenkins_status == *"is running"* ]] &&  [ $(echo `date +%s` - $start_time |bc) -lt ${SHUT_TIMEOUT} ];
    do
        sleep 10;
        jenkins_status=$(ssh  root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} /etc/init.d/jenkins status" 2>/dev/null)
    done
    echo "Force stopping Jenkins service if it wasn't stopped"
    ssh  root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} /etc/init.d/jenkins stop"
    sleep 10
    echo "Jenkins stopped: ${jenkins_status}"
    echo "Suspending Jenkins"
    virsh -c $DST_URL suspend ${JENKINS_VM_NAME}
    # copy disks
    echo "Copying Jenkins disk"
    scp root@${JENKINS_GATE}:/opt/qa/jenkins_disk.qcow2 $curdir/
    echo "Resume Jenkins"
    virsh -c $DST_URL resume ${JENKINS_VM_NAME}
    echo "Update time on Jenkins"
    ssh  root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} '/etc/init.d/ntp stop; \
        ntpdate ntp.cisco.com || ntpdate ntp.ubuntu.com || ntpdate 10.81.254.131; /etc/init.d/ntp start;'"
    echo "Starting Jenkins again"
    ssh  root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} /etc/init.d/jenkins start"
    # copy snapshots
    echo "Copying Jenkins snapshots"
    for i in `virsh -c $DST_URL snapshot-list ${JENKINS_VM_NAME} | awk {'print $1'} | sed -n '/[a-Z]/p' | grep -v Name`;
        do
            virsh -c $DST_URL snapshot-dumpxml ${JENKINS_VM_NAME} $i > $curdir/jenkinsnap/$i.xml;
        done
    # dump configs
    virsh -c $DST_URL dumpxml ${JENKINS_VM_NAME} > $curdir/${JENKINS_VM_NAME}.xml
}

function backup_zuul {

    echo "Suspending Zuul"
    virsh -c $DST_URL suspend ${ZUUL_VM_NAME}
    # copy disks
    echo "Copying Zuul disks"
    scp -r root@${JENKINS_GATE}:/opt/qa/zuul.* $curdir/
    echo "Resume Zuul"
    virsh -c $DST_URL resume ${ZUUL_VM_NAME}
    echo "Update time on Zuul"
    ssh  root@${JENKINS_GATE} "ssh root@${ZUUL_LOCAL_IP} '/etc/init.d/ntp stop; \
     ntpdate ntp.cisco.com || ntpdate ntp.ubuntu.com || ntpdate 10.81.254.131; /etc/init.d/ntp start;'"
    # copy snapshots
    echo "Copying Zuul snapshots"
    for i in `virsh -c $DST_URL snapshot-list ${ZUUL_VM_NAME} | awk {'print $1'} | sed -n '/[a-Z]/p' | grep -v Name | grep -v clear`;
        do
            virsh -c $DST_URL snapshot-dumpxml ${ZUUL_VM_NAME} $i > $curdir/zuulsnap/$i.xml;
        done
    # dump configs
    virsh -c $DST_URL dumpxml ${ZUUL_VM_NAME} > $curdir/${ZUUL_VM_NAME}.xml
}

function checkif_allright {
    if [ -e $curdir/jenkins_disk.qcow2 ] && [ -s $curdir/jenkins_disk.qcow2 ]; then
        echo "Jenkins disk OK!"
    else
        mailall "Jenkins disk fail"
        return 255
    fi
    if [ -e $curdir/jenkins_disk.qcow2 ] && [ -s $curdir/jenkins_disk.qcow2 ]; then
        echo "Jenkins disk OK!"
    else
        mailall "Jenkins disk fail"
        return 255
    fi
    if [ -e $curdir/${JENKINS_VM_NAME}.xml ] && [ -s $curdir/${JENKINS_VM_NAME}.xml ]; then
        echo "Jenkins XML OK!"
    else
        mailall "Jenkins XML fail"
        return 255
    fi
    if [ -e $curdir/${ZUUL_VM_NAME}.xml ] && [ -s $curdir/${ZUUL_VM_NAME}.xml ]; then
        echo "Zuul XML OK!"
    else
        mailall "Zuul XML fail"
        return 255
    fi
    if [ -e $filepath ] && [ -s $filepath ]; then
        echo "Jenkins home directory OK!"
    else
        mailall "Jenkins home directory fail"
        return 255
    fi

}

function snapshot_jenkins {
    echo "Delete todays snapshot if exists for ${JENKINS_VM_NAME}"
    virsh -c $DST_URL snapshot-delete ${JENKINS_VM_NAME} jenkins_bu_$DATE
    echo "Creating snapshot jenkins_bu_$DATE on remote for ${JENKINS_VM_NAME}"
    virsh -c $DST_URL snapshot-create-as ${JENKINS_VM_NAME} jenkins_bu_$DATE
}

function snapshot_zuul {
    echo "Delete todays snapshot if exists for ${ZUUL_VM_NAME}"
    virsh -c $DST_URL snapshot-delete ${ZUUL_VM_NAME} zuul_bu_$DATE
    echo "Creating snapshot zuul_bu_$DATE on remote for ${ZUUL_VM_NAME}"
    virsh -c $DST_URL snapshot-create-as ${ZUUL_VM_NAME} zuul_bu_$DATE
}

function remove_all () {
    stamp=$1
    echo "Removing directory $BU_DIR/$stamp"
    rm -rf $BU_DIR/$stamp
    for vm in ${JENKINS_VM_NAME}_$stamp ${ZUUL_VM_NAME}_$stamp;
    do
        for snapshot in $(virsh snapshot-list $vm | awk {'print $1'} | sed -n '/[a-Z]/p' | grep -v Name);
        do
            echo "Delete snapshot $snapshot from $vm"
            virsh -c $LOCAL_URL snapshot-delete $vm $snapshot
        done
        echo "Destroying $vm"
        virsh -c $LOCAL_URL destroy $vm
        echo "Undefine $vm"
        virsh -c $LOCAL_URL undefine $vm
    done
    echo "Delete on remote snapshot jenkins_bu_${stamp}"
    virsh -c $DST_URL snapshot-delete ${JENKINS_VM_NAME} jenkins_bu_${stamp}
    echo "Delete on remote snapshot zuul_bu_${stamp}"
    virsh -c $DST_URL snapshot-delete ${ZUUL_VM_NAME} zuul_bu_${stamp}

}


function clear_old {

    if [ $(ls $BU_DIR | grep -Eo "^[0-9]+$" | sort -n | wc -l) -gt $LIMIT_BU ]; then
        echo "There are more than  ${LIMIT_BU} backups, removing unnecessary "
        DELLINES=$(ls $BU_DIR | grep -Eo "[0-9]+" | sort -n | head -n-${LIMIT_BU})
        for i in $DELLINES;
        do
            remove_all $i
        done

    else
        echo "Backups are less than ${LIMIT_BU}, not deleting anything";
    fi
}

update_time
prepare_dir $DATE
copy_jenkins_home
copy_jenkins_jobs
backup_jenkins
backup_zuul
checkif_allright
if [ "$?" == 255 ]; then
    echo "Fail with backups!"
    exit 255
fi

snapshot_jenkins
snapshot_zuul
clear_old
