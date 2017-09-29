from lab.test_case_worker import TestCaseWorker


class SocketConnectToPort(TestCaseWorker):

    ARG_IP_PORT = 'ip_port'
    ARG_SOCKET_TIMEOUT = 'socket_timeout'

    @property
    def ip_port(self):
        return self.args[self.ARG_IP_PORT].split(':')

    @property
    def socket_timeout(self):
        return int(self.args[self.ARG_SOCKET_TIMEOUT])

    def check_arguments(self):
        assert len(self.ip_port) == 2, '{}: wrong value {}, should be ip:port'.format(self, self.ip_port)

    def setup_worker(self):
        pass

    def loop_worker(self):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(int(self.socket_timeout))

        ip, port = self.ip_port
        try:
            s.connect((ip, port))
            res = 1
        except (socket.timeout, socket.error):
            res = 0
        finally:
            s.close()
        self.log('status={}'.format(res))
