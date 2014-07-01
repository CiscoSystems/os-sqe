#!/bin/bash

#LAST_DATE=$(ls $BU_DIR | grep -Eo "^[0-9]+$" | sort -n | tail -1)
source ./backup_config

jobsdir=$(mktemp -d /tmp/jobs.XXXXX)
gitdir="/tmp/git_clones"

rm -rf $jobsdir
mkdir -p $jobsdir
echo "Started copying jobs"
jobs=$(ssh root@${JENKINS_GATE} "ssh root@${JENKINS_LOCAL_IP} ls /var/lib/jenkins/jobs/")
for job in $jobs; do
    scp -Cp -o -q "ProxyCommand ssh root@${JENKINS_GATE} nc ${JENKINS_LOCAL_IP} 22"  \
    root@${JENKINS_LOCAL_IP}:/var/lib/jenkins/jobs/${job}/config.xml $jobsdir/${job}.xml
done
echo "Finished copying jobs"


rm -rf $gitdir
mkdir $gitdir
cd $gitdir
git clone https://github.com/CiscoSystems/openstack-sqe.git
cd openstack-sqe/tools/jenkins/backup/jobs/ || exit 1
rm -rf *xml
cp -r $jobsdir/*xml .
git add *xml
git commit -am "Jobs update $(date +%y%m%d) for $LAST_DATE"
git push
rm -rf $jobsdir