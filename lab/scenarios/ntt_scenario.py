from lab.parallelworker import ParallelWorker


class NttScenario(ParallelWorker):
    def check_arguments(self, **kwargs):
        pass

    def setup_worker(self):
        self.get_cloud().os_image_create('csr')
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-cisco-dev/osqe-configs.git', local_repo_dir='os-sqe-tmp/osqe-configs')
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/nfvi-test.git', local_repo_dir='os-sqe-tmp/nfvi-test')
        self._build_node.r_clone_repo(repo_url='http://gitlab.cisco.com/openstack-perf/testbed.git', local_repo_dir='os-sqe-tmp/testbed')

        self._build_node.exe('docker pull cloud-docker.cisco.com/nfvbench')
        self._build_node.exe('yum install kernel-devel kernel-headers -y')
        self._build_node.exe('docker run --rm --privileged -v /lib/modules/$(uname -r):/lib/modules/$(uname -r) -v /usr/src/kernels/$(uname -r):/usr/src/kernels/$(uname -r) cloud-docker.cisco.com/nfvbench nfvbench -h')
        self._build_node.exe('docker run --rm --privileged -v $PWD:/tmp/nfvbench cloud-docker.cisco.com/nfvbench nfvbench_config', in_directory='os-sqe-tmp')

    def loop_worker(self):
        answers = self._build_node.exe('./nfvbench.sh -c os-sqe-tmp/osqe-configs/nfvbench/nfvbench_config.yaml -g trex-local --rate 1500pps --json results.json', in_directory='os-sqe-tmp', is_warn_only=True)
        return answers

    def teardown_worker(self):
        self._build_node.exe('rm -rf os-sqe-tmp')
