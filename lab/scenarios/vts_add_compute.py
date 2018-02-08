from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class VtsAddCompute(TestCaseWorker):

    def check_arguments(self):
        pass
    
    @section('Setup')
    def setup_worker(self):
        pass
    
    @section('Running test')
    def loop_worker(self):
        self.pod.mgm.exe('ciscovim add-computes --setupfile setup_data.yaml comp2 -y')
