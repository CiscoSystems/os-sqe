from lab.parallelworker import ParallelWorker


class SocketConnectToPort(ParallelWorker):

    def __repr__(self):
        return u'SocketConnectToPort{}:{}({}s)'.format(self._socket_ip, self._socket_port, self._socket_timeout)

    def check_config(self):
        try:
            self.log('{}'.format(self))
        except KeyError as ex:
            raise ValueError('{} section {}: no required parameter "{}"'.format(self._yaml_path, self, ex))

    def setup_worker(self):
        pass

    @property
    def _socket_ip(self):
        return self._kwargs['ip-port'].split(':')[0]

    @property
    def _socket_port(self):
        return self._kwargs['ip-port'].split(':')[1]

    @property
    def _socket_timeout(self):
        return int(self._kwargs['socket-timeout'])

    def loop_worker(self):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(int(self._socket_timeout))

        try:
            s.connect((self._socket_ip, self._socket_port))
            res = 1
        except (socket.timeout, socket.error):
            res = 0
        finally:
            s.close()
        self.log('status={}'.format(res))
