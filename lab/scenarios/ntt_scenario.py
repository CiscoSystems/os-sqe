from lab.parallelworker import ParallelWorker


class NttScenario(ParallelWorker):

    def check_config(self):
        if type(self._is_no_cleanup) is not bool:
            raise ValueError('{}: define no-cleanup: True/False')

    @property
    def _is_no_cleanup(self):
        return self._kwargs['no-cleanup']

    def setup_worker(self):
        self.get_mgmt().r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/nfvi-test.git', local_repo_dir='os-sqe-tmp/nfvi-test')
        self.get_mgmt().r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/testbed.git', local_repo_dir='os-sqe-tmp/testbed')
        self.get_mgmt().exe('rm -f nfvbench_config.yaml && cp testbed/{}/nfvbench_config.yaml .'.format(self.get_lab()), in_directory='os-sqe-tmp')

        with open('lab/scenarios/nfvbench.sh', 'r') as f:
            body = f.read()
        self.get_mgmt().r_put_string_as_file_in_dir(string_to_put=body, file_name='execute', in_directory='os-sqe-tmp')
        self.get_mgmt().exe('docker pull cloud-docker.cisco.com/nfvbench')
        self.get_mgmt().exe('yum install kernel-devel kernel-headers -y')
        # self.get_cloud().os_image_create('csr')

    def loop_worker(self):
        ans = []
        for parmaters in ['--rate 1.3Gbps --flow-count 10000', '--rate ndr_pdr --flow-count 10000']:
            ans.append(self.single_run(parameters=parmaters))
        return ans

    def single_run(self, parameters):
        import json

        ans = self.get_mgmt().exe('. execute {} {}'.format(parameters, '--no-cleanup' if self._is_no_cleanup else ''), in_directory='os-sqe-tmp', is_warn_only=True)
        if 'ERROR' in ans:
            raise RuntimeError(ans)
        else:
            res_json_body = self.get_mgmt().r_get_file_from_dir(file_name='results.json', in_directory='os-sqe-tmp')

            suffix = parameters.replace(' ', '_')
            with self.get_lab().open_artifact('nfvbench_results_{}.json'.format(suffix), 'w') as f:
                f.write(res_json_body)
            with self.get_lab().open_artifact('nfvbench_output_{}.txt'.format(suffix), 'w') as f:
                f.write(ans)
            res_json = json.loads(res_json_body)
            res = []
            for mtu, di in res_json['benchmarks']['network']['service_chain']['PVP']['result'][0]['result'].items():
                if 'ndr' in di:
                    for t in ['ndr', 'pdr']:
                        la_min, la_avg, la_max = di[t]['stats']['overall']['min_delay_usec'], di[t]['stats']['overall']['avg_delay_usec'], di[t]['stats']['overall']['max_delay_usec']
                        gbps = di[t]['rate_bps'] / 1e9
                        drop_thr = di[t]['stats']['overall']['drop_rate_percent']
                        res.append('MTU={} {}({:.4f}) rate={:.4f} Gbps latency={:.1f} {:.1f} {:.1f} usec'.format(mtu, t, drop_thr, gbps, la_min, la_avg, la_max))
                else:
                    res.append('MTU={} RT={}'.format(mtu, di['stats']['overall']['rx']['pkt_bit_rate'] + di['stats']['overall']['tx']['pkt_bit_rate']))
            return parameters + '-->' + '; '.join(res)

    def teardown_worker(self):
        if not self._is_no_cleanup:
            self.get_mgmt().exe('rm -rf os-sqe-tmp')

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