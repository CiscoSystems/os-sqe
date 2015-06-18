#!/bin/bash -x

# If a bundle file is present, call tox with the jenkins version of
# the test environment so it is used.  Otherwise, use the normal
# (non-bundle) test environment.  Also, run pbr freeze on the
# resulting environment at the end so that we have a record of exactly
# what packages we ended up testing.
#
# Usage: run-tox.sh VENV
#
# Where VENV is the name of the tox environment to run (specified in the
# project's tox.ini file).

venv=$1
workspace=$2

if [[ -z "$venv" ]]; then
    echo "Usage: $?"
    echo
    echo "VENV: The tox environment to run (eg 'python27')"
    exit 1
fi

function process_testr_artifacts {
    if [ ! -d ".testrepository" ] ; then
        return
    fi

    if [ -f ".testrepository/0.2" ] ; then
        cp .testrepository/0.2 ./testrepository.subunit
    elif [ -f ".testrepository/0" ] ; then
        testr last --subunit > ./testrepository.subunit
    fi
    python ${workspace}/neutron_ci/tools/subunit2html.py ./testrepository.subunit testr_results.html
    SUBUNIT_SIZE=$(du -k ./testrepository.subunit | awk '{print $1}')
    gzip -9 ./testrepository.subunit
    gzip -9 ./testr_results.html

    if [[ "$SUBUNIT_SIZE" -gt 50000 ]]; then
        echo
        echo "testrepository.subunit was > 50 MB of uncompressed data!!!"
        echo "Something is causing tests for this project to log significant amounts"
        echo "of data. This may be writers to python logging, stdout, or stderr."
        echo "Failing this test as a result"
        echo
        exit 1
    fi

    rancount=$(testr last | sed -ne 's/Ran \([0-9]\+\).*tests in.*/\1/p')
    if [ -z "$rancount" ] || [ "$rancount" -eq "0" ] ; then
        echo
        echo "Zero tests were run. At least one test should have been run."
        echo "Failing this test as a result"
        echo
        exit 1
    fi
}

export NOSE_WITH_XUNIT=1
export NOSE_WITH_HTML_OUTPUT=1
export NOSE_HTML_OUT_FILE='nose_results.html'
export TMPDIR=`/bin/mktemp -d`
trap "rm -rf $TMPDIR" EXIT

tox -v -e$venv
result=$?

process_testr_artifacts

exit $result
