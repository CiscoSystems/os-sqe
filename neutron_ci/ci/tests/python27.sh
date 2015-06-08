#!/usr/bin/env bash

# Following environment variables should be defined:
#   NEUTRON_REPO, NEUTRON_REF, NET_CISCO_REPO, NET_CISCO_REF
#   ZUUL_URL, WORKSPACE

set -o xtrace

sudo pip install tox
sudo rm -rf ~/.cache

# Clone networking-cisco repository and checkout ref
git clone -q ${NET_CISCO_REPO}
cd networking-cisco
git fetch ${NET_CISCO_REPO} ${NET_CISCO_REF}
git checkout FETCH_HEAD
git --no-pager log -n1

# Write neutron-ref to test-patches.txt Used by tools/add_neutron_patches.sh
echo ${NEUTRON_REF} >>test-patches.txt

# Set neutron repo
sed -i "s/git:\/\/git.openstack.org\/openstack\/neutron.git/git+${NEUTRON_REPO//\//\\/}/" requirements.txt

# Fix add_neutron_patches.sh
sed -i "s/https:\/\/review.openstack.org\//${ZUUL_URL//\//\\/}/" tools/add_neutron_patches.sh
sed -i "s/rebase master/rebase origin\/master/" tools/add_neutron_patches.sh
sed -i '16iexport HOME=$DIRECTORY' tools/add_neutron_patches.sh
sed -i '17igit config --global user.email "you@example.com"' tools/add_neutron_patches.sh
sed -i '18igit config --global user.name "Your Name"' tools/add_neutron_patches.sh

# Run tests
bash ${WORKSPACE}/neutron_ci/run-tox.sh py27 ${WORKSPACE}
result=$?

exit ${result}
