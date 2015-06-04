#!/bin/sh

DESTINATION=$1

sudo mkdir -p ${DESTINATION}
sudo chown ubuntu:root ${DESTINATION}

# Clone repositories. "RECLONE=True" should be added to localrc
PROJECTS="openstack/requirements.git openstack-dev/pbr.git openstack/cliff.git openstack/oslo.i18n.git"
PROJECTS="${PROJECTS} openstack/oslo.config.git openstack/oslo.messaging.git openstack/oslo.rootwrap.git openstack/oslo.db.git"
PROJECTS="${PROJECTS} openstack/oslo.vmware.git openstack/pycadf.git openstack/stevedore.git openstack/taskflow.git"
PROJECTS="${PROJECTS} openstack/python-keystoneclient.git openstack/python-glanceclient.git openstack/python-cinderclient.git openstack/python-novaclient.git"
PROJECTS="${PROJECTS} openstack/python-swiftclient.git openstack/python-neutronclient.git openstack/keystonemiddleware.git openstack/python-openstackclient.git"
PROJECTS="${PROJECTS} openstack/keystone.git openstack/glance.git openstack/cinder.git openstack/nova.git openstack/tempest.git"
PROJECTS="${PROJECTS} openstack/neutron-lbaas openstack/neutron-vpnaas openstack/neutron-fwaas"
for PROJECT in ${PROJECTS}; do
	NAME=$(echo $PROJECT | grep -P -o '(?<=\/).*(?=.git)')
	PROJECT_DEST=${DESTINATION}${NAME}
	git clone git://git.openstack.org/${PROJECT} ${PROJECT_DEST}
	cd ${PROJECT_DEST} && sudo pip install -r requirements.txt || true
done