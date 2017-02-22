from lab.parallelworker import ParallelWorker


class NttScenario(ParallelWorker):
    def check_arguments(self, **kwargs):
        pass

    def setup_worker(self):
        self.get_cloud().os_image_create('csr')
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/nfvi-test.git', local_repo_dir='os-sqe-tmp/nfvi-test')
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/testbed.git', local_repo_dir='os-sqe-tmp/testbed')

        self._build_node.exe('docker pull cloud-docker.cisco.com/nfvbench')
        self._build_node.exe('yum install kernel-devel kernel-headers -y')
        self._build_node.exe('docker run --rm --privileged -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) -v /usr/src/kernels/$(uname -r):/usr/src/kernels/$(uname -r) cloud-docker.cisco.com/nfvbench nfvbench -h')
        self._build_node.exe('cp testbed/{}/nfvbench_config.yaml .'.format(self.get_lab()), in_directory='os-sqe-tmp')

    def loop_worker(self):
        answers = self._build_node.exe('sudo docker run --rm --privileged --net host --name nfvbench '
                                       '-v $PWD:/tmp/nfvbench '
                                       '-v /etc/hosts:/etc/hosts '
                                       '-v ~/.ssh:/root/.ssh '
                                       '-v /dev:/dev '
                                       '-v ~/openstack-configs:/tmp/nfvbench/openstack '
                                       '-v /lib/modules/$(uname -r):/lib/modules/$(uname -r) '
                                       '-v /usr/src/kernels/$(uname -r):/usr/src/kernels/$(uname -r)  '
                                       'cloud-docker.cisco.com/nfvbench:latest '
                                       '-c nfvbench_config.yaml --rate 1500pps --json results.json', in_directory='os-sqe-tmp', is_warn_only=True)
        return answers

    def teardown_worker(self):
        self._build_node.exe('echo rm -rf os-sqe-tmp')

"""
#!/bin/bash

# Script runs nfvbench tool with all necessary parameters.
# It runs from current working directory. To run nfvbench in this directory:
#   1. copy cfg.default.yaml (run this script with --show-config and redirect output to file)
#       nfvbench.sh --show-config > nfvbench.cfg
#   2. keep defaults for paths to OpenStack files (default is /tmp/nfvbench/openstack)

SPIRENT_CONTAINER="cloud-docker.cisco.com/spirent"
NFVBENCH_CONTAINER="cloud-docker.cisco.com/nfvbench"

if [ -d "/root/openstack-configs" ]; then
    EXTRA_ARGS="-v /root/openstack-configs:/tmp/nfvbench/openstack"
else
    EXTRA_ARGS=""
fi

SPIRENT_COMMAND="docker run --privileged --net host -td ${SPIRENT_CONTAINER}"
SPIRENT_CONTAINER_ID="$($SPIRENT_COMMAND)"

KERNEL=$(uname -r)

NFVBENCH_COMMAND="docker run \
    --rm \
    --privileged \
    --net host \
    -it \
    --volumes-from ${SPIRENT_CONTAINER_ID} \
    -v ${PWD}:/tmp/nfvbench \
    -v /etc/hosts:/etc/hosts \
    -v ${HOME}/.ssh:/root/.ssh \
    -v /dev:/dev \
    -v /lib/modules/${KERNEL}:/lib/modules/${KERNEL} \
    -v /usr/src/kernels/${KERNEL}:/usr/src/kernels/${KERNEL} \
    ${EXTRA_ARGS} \
    ${NFVBENCH_CONTAINER} nfvbench"

$NFVBENCH_COMMAND $*

docker rm -f $SPIRENT_CONTAINER_ID
"""