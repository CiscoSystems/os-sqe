#!/bin/bash
source $WORKSPACE/tempest/.venv/bin/activate
tests="$WORKSPACE/openstack-sqe/tools/tempest-scripts/tests_set"
cd $WORKSPACE/tempest/
rm -rf .testrepository || :
testr init || :
if [ -s "$tests" ]; then
    testr run --load-list "$tests" --subunit  | subunit-2to1 | tools/colorizer.py || :
else
    testr run "$REG" --subunit | subunit-2to1 | tools/colorizer.py || :
fi
suffix=$(date +%s)
results=${WORKSPACE}/openstack-sqe/nosetests_${suffix}.xml
testr last --subunit | subunit-1to2 | subunit2junitxml --output-to="$results" || :
testr last --subunit > "${WORKSPACE}/openstack-sqe/testr_results_${suffix}.subunit"

#failed_tests=$(testr failing --list | grep -Eo "tempest[\._A-z]+" | sed "s/\(.*\)\..*\(JSON\)*\(XML\)*/\1/g" | sort -u)
#echo $failed_tests > "$WORKSPACE/openstack-sqe/failed"
#export REG=$(echo $failed_tests | xargs echo | sed 's/ /.*\|/g' | sed "s/\(.*$\)/(\1)/g")

