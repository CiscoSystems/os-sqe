# PARAMS_BASE - global environment variable. It is a connection string to database that contains
#               test parameters. If you leave it undefined the test will not get parameters
#               from a database but you define them manually.
test=$1
publish_to=$2
publish_path=$3
publish_login=$4
publish_pass=$5

#Removing cache on the node
sudo rm -rf ~/.cache
sudo pip install --upgrade ndg-httpsclient
sudo pip install -H -r requirements.txt

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

echo "gzip logs folder"
cd ${WORKSPACE}
find logs -regex '.*log$' -exec gzip -9 {} \;

if [[ -n "${publish_to}" ]]; then
    echo "Publish test results..."
    logspath=${publish_path}/${JOB_NAME}/
    cp -vr logs ${BUILD_NUMBER}
    sshpass -p ${publish_pass} ssh -o StrictHostKeyChecking=no ${publish_login}@${publish_to} mkdir -p ${logspath}
    sshpass -p ${publish_pass} rsync -ave "ssh -o StrictHostKeyChecking=no" ${BUILD_NUMBER} ${publish_login}@${publish_to}:${logspath}
fi

if [[ $rc != 0 ]]
then
    echo "Test FAILED!"
    exit $rc
fi
echo "Test PASSED!"