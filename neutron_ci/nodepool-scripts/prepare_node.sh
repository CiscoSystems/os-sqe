#!/bin/bash

WORK_DIR=`pwd`

cat >>/home/ubuntu/.ssh/authorized_keys <<EOF
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCj9HsmH5E2hlwOXpBd8FFQY0fxMBJBiFeAc/I9ds9WQMjeuLnYWICE2DCX7AoMSwPLl/IwKQZGV/Vt3nB12/EKvTMx6yCgfPOGrejzYYUhDSxJwuFg5KHDuLHXcUjDz/uAn2mzEDwPqtsxRSeKB/IYa7cn2VdgmrIi7PPc2/Gzk7CnYpqwMjMr1A9BxJz41yCN4gkNxk8LFxVtiAFQRuPVAU06yzEbQHPzPCZbVOpBo+TZcEOIepCy0DLrjcwEa26uBEeN13aGWaRuhtztYngtrpK1d4ivVGprYjvrpRGinYP2ETaX13UtseSz4pKnip/JbL+kCkuAxD3/UloK3v5p nfedotov@cisco.com
EOF

ssh-keygen -P '' -f /home/ubuntu/.ssh/id_rsa
cat /home/ubuntu/.ssh/id_rsa.pub >> /home/ubuntu/.ssh/authorized_keys

echo "apt_preserve_sources_list: true" | sudo tee /etc/cloud/cloud.cfg.d/99-local-mirror-only.cfg
sudo cp sources.list /etc/apt/
sudo apt-get update

# Install java
sudo apt-get install -y openjdk-6-jre

# Install packages
sudo apt-get install -y python-pip libxml2-dev libxslt1-dev python-dev zlib1g-dev sshpass git mysql-client libmysqlclient-dev
sudo pip install ecdsa junitxml

# Install Cisco ncclient
sudo pip uninstall -y ncclient || :
NCCLIENT_DIR=/opt/git/ncclient
sudo mkdir -p ${NCCLIENT_DIR}
sudo git clone --depth=1 -b master https://github.com/CiscoSystems/ncclient.git ${NCCLIENT_DIR}
cd ${NCCLIENT_DIR} && sudo python setup.py install && cd -

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

# Clone repositories. "RECLONE=True" should be added to localrc
PROJECTS="openstack/requirements.git openstack-dev/pbr.git openstack/cliff.git openstack/oslo.i18n.git"
PROJECTS="${PROJECTS} openstack/oslo.config.git openstack/oslo.messaging.git openstack/oslo.rootwrap.git openstack/oslo.db.git"
PROJECTS="${PROJECTS} openstack/oslo.vmware.git openstack/pycadf.git openstack/stevedore.git openstack/taskflow.git"
PROJECTS="${PROJECTS} openstack/python-keystoneclient.git openstack/python-glanceclient.git openstack/python-cinderclient.git openstack/python-novaclient.git"
PROJECTS="${PROJECTS} openstack/python-swiftclient.git openstack/python-neutronclient.git openstack/keystonemiddleware.git openstack/python-openstackclient.git"
PROJECTS="${PROJECTS} openstack/keystone.git openstack/glance.git openstack/cinder.git openstack/nova.git openstack/tempest.git"
for PROJECT in ${PROJECTS}; do
	NAME=$(echo $PROJECT | grep -P -o '(?<=\/).*(?=.git)')
	PROJECT_DEST=/opt/stack/${NAME}
	sudo git clone git://git.openstack.org/${PROJECT} ${PROJECT_DEST}
	cd ${PROJECT_DEST} && sudo pip install -r requirements.txt || true
done
cd ${WORK_DIR}
