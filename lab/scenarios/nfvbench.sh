NFVBENCH_CONTAINER="cloud-docker.cisco.com/nfvbench"
MERCURY_VERSION=$(cat /etc/cisco-mercury-release)
KERNEL=$(uname -r)
V_KERNEL="-v /lib/modules/${KERNEL}:/lib/modules/${KERNEL} -v /usr/src/kernels/${KERNEL}:/usr/src/kernels/${KERNEL}"
V_PARAMS="-v \${PWD}:/tmp/nfvbench -v /etc/hosts:/etc/hosts -v ${HOME}/.ssh:/root/.ssh -v /dev:/dev ${V_KERNEL} -v /root/openstack-configs:/tmp/nfvbench/openstack"
ALL_PARAMS="--privileged --net host ${V_PARAMS} --name nfvbench_${MERCURY_VERSION} ${NFVBENCH_CONTAINER}"

grep -q -F "alias start_nfv=" /root/.bashrc || echo alias start_nfv=\'docker run -d ${ALL_PARAMS}\' >> /root/.bashrc

docker run --rm -it ${ALL_PARAMS} nfvbench -c /tmp/nfvbench/nfvbench_config.yaml --json /tmp/nfvbench/results.json $*
