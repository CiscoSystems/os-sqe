from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class PingScenario(TestCaseWorker):
    ARG_MANDATORY_HOW = 'how'
    ARG_MANDATORY_N_PACKETS = 'n_packets'
    STATUS_PING_START = 'status=PingStart'

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
        cmd = 'ping -c {} {}'.format(self.n_packets, srv2.ips[0])
        self.log(self.STATUS_PING_START + ' ' + cmd)
        ans = srv1.console_exe(cmd)
        if 'rtt min' in ans[-1]:
            self.passed('{} {} -> {} {} {}'.format(srv1, srv1.ips[0], srv2, srv2.ips[0], ans[-2]))
        else:
            self.failed(message=ans[-1],is_stop_running=False)

    def loop_worker(self):
        if self.how == 'internal':
            self.internal()
