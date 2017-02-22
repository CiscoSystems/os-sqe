NFVBENCH_CONTAINER="cloud-docker.cisco.com/nfvbench"

KERNEL=$(uname -r)

NFVBENCH_COMMAND="docker run \
    --rm \
    --privileged \
    --net host \
    -it \
    -v ${PWD}:/tmp/nfvbench \
    -v /etc/hosts:/etc/hosts \
    -v ${HOME}/.ssh:/root/.ssh \
    -v /dev:/dev \
    -v /lib/modules/${KERNEL}:/lib/modules/${KERNEL} \
    -v /usr/src/kernels/${KERNEL}:/usr/src/kernels/${KERNEL} \
    -v /root/openstack-configs:/tmp/nfvbench/openstack \
    ${NFVBENCH_CONTAINER} nfvbench"

$NFVBENCH_COMMAND -c /tmp/nfvbench/nfvbench_config.yaml {XXXXX} --json /tmp/nfvbench/results.json
