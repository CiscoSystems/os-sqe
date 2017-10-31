from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class NttScenario(TestCaseWorker):

    ARG_RUN_INSIDE = 'run_inside'
    ARG_CSR_ARGS = 'csr_args'
    ARG_NFVBENCH_ARGS = 'nfvbench_args'

    def check_arguments(self):
        possible_modes = ['csr', 'nfvbench', 'both']
        assert self.run_inside in possible_modes

    @property
    def run_inside(self):
        return self.args[self.ARG_RUN_INSIDE]

    @property
    def csr_args(self):
        return self.args[self.ARG_CSR_ARGS]

    @property
    def nfvbench_args(self):
        return self.args[self.ARG_NFVBENCH_ARGS] + (' --no-cleanup' if self.test_case.is_noclean else '')

    @property
    def perf_reports_repo_dir(self):
        return '~/reports_repo'

    @property
    def csr_repo_dir(self):
        return '~/csr_repo'

    @property
    def is_sriov(self):
        return self.args['is-sriov']

    @section(message='Setting up (estimate 100 secs)')
    def setup_worker(self):
        from os import path
        from lab.cloud.cloud_image import CloudImage

        # self.pod.mgmt.r_configure_mx_and_nat()
        if self.run_inside in ['both', 'csr']:
            self.pod.mgmt.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/nfvi-test.git', local_repo_dir=self.csr_repo_dir)

            url, checksum, size, _, _, loc_rel_path = CloudImage.read_image_properties(name='CSR1KV')
            loc_abs_path = path.join(self.csr_repo_dir, path.basename(loc_rel_path))
            self.pod.mgm.r_curl(url='http://172.29.173.233/cloud-images/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2', size=size, checksum=checksum, loc_abs_path=loc_abs_path)
        if self.run_inside in ['both', 'nfvbench']:
            if len(self.pod.mgm.intel_nics_dic) < 2:
                raise RuntimeError('{}: there is no Intel NIC to inject T-Rex traffic'.format(self.pod.mgmt))
            self.args['is-sriov'] = len(self.pod.computes[0].intel_virtual_nics_dic) >= 8
            self.pod.mgm.r_clone_repo(repo_url='git@wwwin-gitlab-sjc.cisco.com:mercury/perf-reports.git', local_repo_dir=self.perf_reports_repo_dir)
            if self.pod.driver == 'vts':
                for tor_name, tor_port in self.pod.setup_data_dic['NFVBENCH']['tor_info'].items():
                    tor_port = 'Ethernet' + tor_port[-4:]
                    self.pod.vtc.r_vtc_add_host_to_inventory(server_name='nfvbench_tg', tor_name=tor_name, tor_port=tor_port)

            # trex_mode = VimTor.TREX_MODE_CSR if self.what_to_run == 'both' else VimTor.TREX_MODE_NFVBENCH
            # [x.n9_trex_port(mode=trex_mode) for x in self.pod.vim_tors]
        self.pod.mgm.exe(cmd='git config --global user.name "Performance team" && git config --global user.email "perf-team@cisco.com" && git config --global push.default simple', is_as_sqe=True)
        self.cloud.os_quota_set()

    def loop_worker(self):
        if self.run_inside in ['csr', 'both']:
            self.csr_run()

        if self.run_inside in ['nfvbench', 'both']:
            self.nfvbench_run(is_sriov=False)
            if self.is_sriov and 'PVVP' not in self.nfvbench_args:
                self.nfvbench_run(is_sriov=True)

    def csr_run(self):
        from lab.cloud.cloud_server import CloudServer

        cmd = 'source ~/openrc && ./{} # <number of CSRs> <number of CSR per compute> <total time to sleep between successive nova boot'.format(self.csr_args)
        ans = self.pod.mgm.exe(cmd=cmd, in_dir=self.csr_repo_dir, is_as_sqe=True)

        with self.pod.open_artifact('csr_script_output.txt', 'w') as f:
            f.write(cmd + '\n')
            f.write(ans)
        if 'ERROR' in ans:
            errors = [x.split('\r\n')[0] for x in ans.split('ERROR')[1:]]
            errors = [x for x in errors if 'No hypervisor matching' not in x]
            if errors:
                self.fail('# errors {} the first is {}'.format(len(errors), errors[0]), is_stop_running=True)
        servers = CloudServer.list(cloud=self.cloud)
        CloudServer.wait(servers=servers, status='ACTIVE')

    def nfvbench_run(self, is_sriov):
        from os import path

        if is_sriov:
            cfg = "-c \"{flavor: {extra_specs : {'hw:numa_nodes': 2}}, internal_networks: {left: {physical_network: phys_sriov0, segmentation_id: 3}, right: {physical_network: phys_sriov0, segmentation_id: 4}}}\" --sriov "
        else:
            cfg = ' '

        cmd = 'nfvbench ' + cfg + self.nfvbench_args + ' --std-json /tmp/nfvbench '
        ans = self.pod.mgm.exe(cmd, is_warn_only=True)  # nfvbench --service-chain EXT --rate 1Mpps --duration 10 --std-json /tmp/nfvbench
        with self.pod.open_artifact('nfvbench_' + self.nfvbench_args.replace(' ', '_').replace('/', '_') + ('_sriov' if is_sriov else '') + '.txt', 'w') as f:
            f.write(cmd + '\n')
            f.write(ans)

        if 'ERROR' in ans:
            self.fail(ans.split('ERROR')[-1][-200:], is_stop_running=True)
        elif 'Error' in ans:
            self.fail(ans, is_stop_running=True)
        else:
            with self.pod.open_artifact('final_report.txt', 'a') as f:
                f.write('csr: ' + self.csr_args + ' nfvbench ' + self.nfvbench_args + '\n')
                f.write(ans.split('Run Summary:')[-1])
                f.write('\n' + 80 * '=' + '\n\n')
            json_name1 = path.basename(ans.split('Saving results in json file:')[-1].split('...')[0].strip())
            date = ans.split('Date: ')[-1][:19].replace(' ', '-').replace(':', '-')
            json_name2 = ('SRIOV-' if is_sriov else '') + json_name1 + '.' + date + '.' + self.pod.name
            self.pod.mgm.exe(cmd='sudo mv /root/nfvbench/{0} {1} && git pull && echo {1} >> catalog && git add --all && git commit -m "report on $(hostname) at $(date)" && git push'.format(json_name1, json_name2),
                             in_dir=self.perf_reports_repo_dir, is_as_sqe=True)
            res_json_body = self.pod.mgm.r_get_file_from_dir(rem_rel_path=json_name2, in_dir=self.perf_reports_repo_dir)
            self.process_nfvbench_json(res_json_body=res_json_body)

    def process_nfvbench_json(self, res_json_body):
        import json

        j = json.loads(res_json_body)

        with self.pod.open_artifact('{}-{}-{}-{}.json'.format(j['openstack_spec']['vswitch'], j['config']['service_chain'], j['config']['service_chain_count'], j['config']['flow_count']), 'w') as f:
            f.write(res_json_body)

        res = []
        for mtu, di in j['benchmarks']['network']['service_chain'][j['config']['service_chain']]['result']['result'].items():
            if 'ndr' in di:
                for t in ['ndr', 'pdr']:
                    la_min, la_avg, la_max = di[t]['stats']['overall']['min_delay_usec'], di[t]['stats']['overall']['avg_delay_usec'], di[t]['stats']['overall']['max_delay_usec']
                    gbps = di[t]['rate_bps'] / 1e9
                    if gbps < 1.2:
                        self.fail('GBPS < 1.2', is_stop_running=False)
                    drop_thr = di[t]['stats']['overall']['drop_percentage']
                    res.append('size={} {}({:.4f}) rate={:.4f} Gbps latency={:.1f} {:.1f} {:.1f} usec\n'.format(mtu, t, drop_thr, gbps, la_min, la_avg, la_max))
            else:
                gbps = (di['stats']['overall']['rx']['pkt_bit_rate'] + di['stats']['overall']['tx']['pkt_bit_rate']) / 1e9
                res.append('size={} rate={} Gbps'.format(mtu, gbps))
        self.worker_data = '; '.join(res)

    # @section(message='Tearing down (estimate 100 sec)')
    # def teardown_worker(self):
    #     if not self.test_case.is_noclean:
    #         self.cloud.os_cleanup(is_all=False)
    #         if self.pod.driver == 'vts':
    #             self.pod.vtc.r_vtc_delete_openstack()
    #         # self.pod.mgmt.exe('rm -rf *')


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

lsmod | grep igb_uio
cd /opt/trex/v2.18
./t-rex-64 -i --no-scapy-server
cat /tmp/trex

docker pull cloud-docker.cisco.com/nfvbench
        par = '--privileged --net host ' \
              '-v {cfg}:/tmp/nfvbench -v /etc/hosts:/etc/hosts -v /root/.ssh:/root/.ssh -v /dev:/dev -v /root/openstack-configs:/tmp/nfvbench/openstack ' \
              '-v /lib/modules/{ker}:/lib/modules/{ker} -v /usr/src/kernels/{ker}:/usr/src/kernels/{ker} '.format(cfg=self._nfv_config_dir, ker=ker.strip())
        alias = "sed -i '/sqe_nfv/d' /root/.bashrc && echo \"alias sqe_nfv=\'docker run -d {} --name nfvbench_{}  cloud-docker.cisco.com/nfvbench\'\" >> /root/.bashrc".format(par, tag)
        self.get_mgmt().exe(alias)
        self._kwargs['nfvbench-cmd'] = 'docker run --rm -it ' + par + '--name nfvbench_sqe_auto cloud-docker.cisco.com/nfvbench nfvbench -c /tmp/nfvbench/{}-config.yaml --json /tmp/nfvbench/results.json'.format(self.get_lab())



ansible-playbook -e @/root/openstack-configs/setup_data.yaml -e @/root/openstack-configs/docker.yaml -e @/root/openstack-configs/defaults.yaml /root/installer-8449/bootstrap/playbooks/nfvbench-install.yaml

nfvbench --show-config


nfvbench --rate 1Mpps --duration 10 --std-json /tmp/nfvbench

nfvbench -c "{flavor: {extra_specs : {'hw:numa_nodes': 2}}, internal_networks: {left: {physical_network: phys_sriov0, segmentation_id: 3}, right: {physical_network: phys_sriov1, segmentation_id: 4}}}" --rate 1Mpps --duration 10 --std-json /tmp/nfvbench --sriov
nfvbench -c "{internal_networks: {left: {physical_network: phys_sriov0, segmentation_id: 3}, right: {physical_network: phys_sriov0, segmentation_id: 4}}}" --rate 1Mpps --duration 10 --service-chain-count 10 --std-json /tmp/nfvbench --sriov

"""
