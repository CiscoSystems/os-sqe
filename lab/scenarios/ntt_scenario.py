from lab.parallelworker import ParallelWorker


class NttScenario(ParallelWorker):
    def check_arguments(self, **kwargs):
        if 'pauses' not in kwargs or type(kwargs['pauses']) is not list:
            raise ValueError('{}: specify pauses: [5, 4, 3, 2, 1]'.format(self))
        self._n_repeats = len(kwargs['pauses'])

    def setup_worker(self):
        import os

        for file_name in os.listdir('lab/scenarios/csr_bash'):
            with open('lab/scenarios/csr_bash/' + file_name, 'r') as f:
                body = f.read()
            self._build_node.r_put_string_as_file_in_dir(string_to_put=body, file_name=file_name, in_directory='ntt_scenario')
        self._build_node.exe('chmod +x *', in_directory='ntt_scenario')
        self._build_node.r_get_remote_file(url='http://172.29.173.233/csr/csr1000v-universalk9.03.16.00.S.155-3.S-ext.qcow2', to_directory='ntt_scenario')
        self._build_node.exe('mkdir -p ntt_scenario/cfg')

    def loop_worker(self):
        pause = self._kwargs['pauses'][self._loop_counter]
        answers = self._build_node.exe('source $HOME/openstack-configs/openrc && unalias cp && . csr_scenario.sh -l {} -d {}'.format(10, pause), in_directory='ntt_scenario', is_warn_only=True)
        return answers

    def teardown_worker(self):
        self._build_node.exe('rm -rf ntt_scenario /tmp/tmp.*')
