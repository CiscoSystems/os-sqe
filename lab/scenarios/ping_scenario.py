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

    @section('Ping servers')
    def internal(self):
        self.cloud.os_all()
        ans = self.cloud.servers[0].console_exe('ping -c {} {}'.format(self.n_packets, self.cloud.servers[1].ips[0]))
        if '{0} packets transmitted, {0} received, 0% packet loss'.format(self.n_packets) not in ans:
            raise RuntimeError(ans)
        return 'ping ok'

    def loop_worker(self):
        if self.how == 'internal':
            self.internal()
