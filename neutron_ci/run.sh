# PARAMS_BASE - global environment variable. It is a connection string to database that contains
#               test parameters. If you leave it undefined the test will not get parameters
#               from a database but you define them manually.
test=$1
publish_to=$2
publish_path=$3
publish_login=$4
publish_pass=$5

sudo pip install -r requirements.txt

if [[ -n "${PARAMS_BASE}" ]]; then
    echo "Get parameters..."
    python tools/parameters.py allocate --connection=${PARAMS_BASE} --wait > params.sh
    source params.sh
    echo "*********************** Parameters *********************** "
    cat params.sh
    echo "********************************************************** "
fi

nosetests ${test}
rc=$?

if [[ -n "${PARAMS_BASE}" ]]; then
    echo "Release parameters..."
    python tools/parameters.py release --connection=${PARAMS_BASE} --id=${PARAM_ID}
fi

if [[ -n "${publish_to}" ]]; then
    echo "Publish test results..."
    files='console.txt local.conf'
    logspath=${publish_path}/${JOB_NAME}/${BUILD_NUMBER}/
    sshpass -p ${publish_pass} ssh -o StrictHostKeyChecking=no ${publish_login}@${publish_to} mkdir -p ${logspath}
    sshpass -p ${publish_pass} rsync -ave "ssh -o StrictHostKeyChecking=no" ${files} ${publish_login}@${publish_to}:${logspath}
    sshpass -p ${publish_pass} rsync -ave "ssh -o StrictHostKeyChecking=no" logs ${publish_login}@${publish_to}:${logspath}

    sshpass -p ${publish_pass} ssh -o StrictHostKeyChecking=no ${publish_login}@${publish_to} gzip -9 "${logspath}*"
    sshpass -p ${publish_pass} ssh -o StrictHostKeyChecking=no ${publish_login}@${publish_to} gzip -9 "${logspath}/logs/*"
fi

if [[ $rc != 0 ]]
then
    echo "Test FAILED!"
    exit $rc
fi
echo "Test PASSED!"