#!/bin/bash

WORK_DIR=`pwd`

bash ./prepare_jenkins_node.sh

ssh-keygen -P '' -f /home/ubuntu/.ssh/id_rsa
cat /home/ubuntu/.ssh/id_rsa.pub >> /home/ubuntu/.ssh/authorized_keys

# Cache devstack dependencies
DEVSTACK=/opt/git/openstack-dev/devstack
sudo mkdir -p ${DEVSTACK}
sudo git clone --depth 1 https://github.com/openstack-dev/devstack.git ${DEVSTACK}
#wget https://raw.githubusercontent.com/openstack-infra/config/master/modules/openstack_project/files/nodepool/scripts/cache_devstack.py
#wget https://raw.githubusercontent.com/openstack-infra/config/master/modules/openstack_project/files/nodepool/scripts/common.py
DISTRIB_CODENAME=`lsb_release -sc`
python ./cache_devstack.py ${DISTRIB_CODENAME}

# Install bash 4.2
wget http://launchpadlibrarian.net/135683014/bash_4.2-5ubuntu3_amd64.deb
sudo dpkg -i ./bash_4.2-5ubuntu3_amd64.deb

./clone_repositories.sh /opt/stack/

cd ${WORK_DIR}
