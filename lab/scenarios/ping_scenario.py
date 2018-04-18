from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class PingScenario(TestCaseWorker):
    ARG_MANDATORY_HOW = 'how'
    ARG_MANDATORY_N_PACKETS = 'n_packets'

    @property
    def how(self):
        return self.args[self.ARG_MANDATORY_HOW]

    @property
    def n_packets(self):
        return self.args[self.ARG_MANDATORY_N_PACKETS]

    def check_arguments(self):
        assert self.n_packets > 1
        assert self.how in ['internal', 'from_mgm']

    def setup_worker(self):
        pass

    def internal(self):
        srv1, srv2 = self.cloud.servers[0], self.cloud.servers[1]
        ans = srv1.console_exe('ping -c {} {}'.format(self.n_packets, srv2.ips[0]))
        if '{0} packets transmitted, {0} received, 0% packet loss'.format(self.n_packets) not in ans:
            self.failed(message=ans.split('\n')[-1],is_stop_running=False)
        self.passed('ping {} {} -> {} {} ok'.format(srv1, srv1.ips[0], srv2, srv2.ips[0]))

    def loop_worker(self):
        if self.how == 'internal':
            self.internal()
