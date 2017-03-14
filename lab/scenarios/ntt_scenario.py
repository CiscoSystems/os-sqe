from lab.parallelworker import ParallelWorker
from lab.decorators import section


class NttScenario(ParallelWorker):

    def check_config(self):
        if type(self._is_no_cleanup) is not bool:
            raise ValueError('{}: define no-cleanup: True/False'.format(self))

        possible_modes = ['csr', 'nfvbench', 'both']
        if self._what_to_run not in possible_modes:
            raise ValueError('{}: what-to-run must on of {}'.format(self, possible_modes))
        return 'run {}, # CSR {}, sleep {},  chain {}, # chains {}, # flows {}, frame size {}, no-cleanup {}'.format(self._what_to_run, self._csr_per_compute, self._csr_sleep,
                                                                                                                     self._chain_type, self._chain_count, self._flow_count, self._frame_size, self._is_no_cleanup)

    @property
    def _is_no_cleanup(self):
        return self._kwargs['no-cleanup']

    @property
    def _what_to_run(self):
        return self._kwargs['what-to-run']

    @property
    def _csr_per_compute(self):
        return self._kwargs['csr-per-compute']

    @property
    def _csr_sleep(self):
        return self._kwargs['csr-sleep']

    @property
    def _chain_type(self):
        return self._kwargs['chain-type']

    @property
    def _chain_count(self):
        return self._kwargs['chain-count']

    @property
    def _flow_count(self):
        return self._kwargs['flow-count']

    @property
    def _frame_size(self):
        return self._kwargs['frame-size']

    @property
    def _tmp_dir(self):
        return self._kwargs['tmp-dir']

    @section(message='Setting up', estimated_time=100)
    def setup_worker(self):
        self._kwargs['tmp-dir'] = '/var/tmp/os-sqe-tmp/'

        self.get_mgmt().exe('rm -rf {}'.format(self._tmp_dir))
        if self._what_to_run in ['both', 'csr']:
            self.get_mgmt().r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/nfvi-test.git', local_repo_dir=self._tmp_dir + 'nfvi-test')
            self.get_mgmt().r_get_remote_file(url='http://172.29.173.233/csr/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2', to_directory=self._tmp_dir + 'nfvi-test')
        if self._what_to_run in ['both', 'nfvbench']:
            self.get_mgmt().r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/testbed.git', local_repo_dir=self._tmp_dir + 'testbed')
            self.get_mgmt().exe('rm -f nfvbench_config.yaml && cp testbed/{}/nfvbench_config.yaml .'.format(self.get_lab()), in_directory=self._tmp_dir)

            with open('lab/scenarios/nfvbench.sh', 'r') as f:
                body = f.read()
            self.get_mgmt().r_put_string_as_file_in_dir(string_to_put=body, file_name='execute', in_directory=self._tmp_dir)
            self.get_mgmt().exe('docker pull cloud-docker.cisco.com/nfvbench')
            self.get_mgmt().exe('yum install kernel-devel kernel-headers -y')

        self.get_cloud().os_cleanup(is_all=True)

    def loop_worker(self):
        if self._what_to_run in ['csr', 'both']:
            self.csr_run()

        if self._what_to_run in ['nfvbench', 'both']:
            self.single_nfvbench_run(parameters='--rate 1.3Gbps --service-chain {} --service-chain-count {} --flow-count {}'.format(self._chain_type, self._chain_count, self._flow_count))

    def csr_run(self):

        n_csr = self._csr_per_compute if int(self._csr_per_compute) == 1 else int(self._csr_per_compute) * len(self.get_cloud().get_computes())
        cmd = 'source $HOME/openstack-configs/openrc && ./csr_create.sh  {} {} {}'.format(n_csr, self._csr_per_compute, self._csr_sleep)
        ans = self.get_mgmt().exe(cmd, in_directory=self._tmp_dir + 'nfvi-test')

        with self.get_lab().open_artifact('csr_create_output.txt', 'w') as f:
            f.write(cmd + '\n')
            f.write(ans)
        if 'ERROR' in ans:
            raise RuntimeError(ans.split('ERROR')[1][:200])

    def single_nfvbench_run(self, parameters):
        import json

        cmd = '. execute {} {}'.format(parameters, '--no-cleanup' if self._is_no_cleanup else '')
        ans = self.get_mgmt().exe(cmd, in_directory=self._tmp_dir, is_warn_only=True)
        with self.get_lab().open_artifact('nfvbench_output.txt', 'w') as f:
            f.write(cmd + '\n')
            f.write(ans)

        if 'ERROR' in ans:
            raise RuntimeError(ans.split('ERROR')[1][:200])
        else:
            res_json_body = self.get_mgmt().r_get_file_from_dir(file_name='results.json', in_directory=self._tmp_dir)

            with self.get_lab().open_artifact('{}-{}-{}.json'.format(self._chain_type, self._chain_count, self._flow_count, self._frame_size), 'w') as f:
                f.write(res_json_body)
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

    @section(message='Tearing down', estimated_time=30)
    def teardown_worker(self):
        if not self._is_no_cleanup:
            self.get_cloud().os_cleanup(is_all=True)
            self.get_mgmt().exe('rm -rf ' + self._tmp_dir)

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