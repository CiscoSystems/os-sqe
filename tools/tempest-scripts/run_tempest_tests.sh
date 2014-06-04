#!/bin/bash
source $WORKSPACE/tempest/.venv/bin/activate
source $WORKSPACE/openstack-sqe/openrc
cd $WORKSPACE/tempest/
testr init || :
testr run --subunit | subunit-2to1 | tools/colorizer.py || :
testr last --subunit | subunit-1to2 | subunit2junitxml --output-to="${WORKSPACE}/nosetests.xml" || :

