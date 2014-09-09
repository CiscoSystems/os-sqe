#!/bin/bash

WORK_DIR=`pwd`

bash ./prepare_jenkins_node.sh

ssh-keygen -P '' -f /home/ubuntu/.ssh/id_rsa
cat /home/ubuntu/.ssh/id_rsa.pub >> /home/ubuntu/.ssh/authorized_keys

# Install packages
sudo apt-get install -y libxml2-dev libxslt1-dev zlib1g-dev sshpass mysql-client libmysqlclient-dev

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
