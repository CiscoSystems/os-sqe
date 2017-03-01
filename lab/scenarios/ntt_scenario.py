from lab.parallelworker import ParallelWorker


class NttScenario(ParallelWorker):
    def check_arguments(self, **kwargs):
        if type(self._is_no_cleanup) is not bool:
            raise ValueError('{}: define no-cleanup: True/False')

    @property
    def _is_no_cleanup(self):
        return self._kwargs['no-cleanup']

    def setup_worker(self):
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/nfvi-test.git', local_repo_dir='os-sqe-tmp/nfvi-test')
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/testbed.git', local_repo_dir='os-sqe-tmp/testbed')
        self._build_node.exe('rm -f nfvbench_config.yaml && cp testbed/{}/nfvbench_config.yaml .'.format(self.get_lab()), in_directory='os-sqe-tmp')

        with open('lab/scenarios/nfvbench.sh', 'r') as f:
            body = f.read()
        self._build_node.r_put_string_as_file_in_dir(string_to_put=body, file_name='execute', in_directory='os-sqe-tmp')
        self._build_node.exe('docker pull cloud-docker.cisco.com/nfvbench')
        self._build_node.exe('yum install kernel-devel kernel-headers -y')
        # self.get_cloud().os_image_create('csr')

    def loop_worker(self):
        ans = []
        for parmaters in ['--rate ndr_pdr --flow-count 10000', '--rate 1.3Gbps']:
            ans.append(self.single_run(parameters=parmaters))
        return ans

    def single_run(self, parameters):
        import json

        ans = self._build_node.exe('. execute {} {}'.format(parameters, '--no-cleanup' if self._is_no_cleanup else ''), in_directory='os-sqe-tmp', is_warn_only=True)
        if 'ERROR' in ans:
            raise RuntimeError(ans)
        else:
            res_json_body = self._build_node.r_get_file_from_dir(file_name='results.json', in_directory='os-sqe-tmp')

            suffix = parameters.replace(' ', '_')
            with self.get_lab().open_artifact('nfvbench_results_{}.json'.format(suffix), 'w') as f:
                f.write(res_json_body)
            with self.get_lab().open_artifact('nfvbench_output_{}.txt'.format(suffix), 'w') as f:
                f.write(ans)
            res_json = json.loads(res_json_body)
            res = []
            for mtu, di in res_json['benchmarks']['network']['service_chain']['PVP']['result'][0]['result'].items():
                res.append('MTU={} RT={}'.format(mtu, di['stats']['overall']['rx']['pkt_bit_rate'] + di['stats']['overall']['tx']['pkt_bit_rate']))
            return parameters + '-->' + '; '.join(res)

    def teardown_worker(self):
        if not self._is_no_cleanup:
            self._build_node.exe('rm -rf os-sqe-tmp')

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