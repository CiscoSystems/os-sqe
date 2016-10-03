from lab.worker import Worker


class SocketConnectToPort(Worker):

    def __repr__(self):
        return u'SocketConnectToPort{}:{}({}s)'.format(self._ip, self._port, self._timeout)

    # noinspection PyAttributeOutsideInit
    def setup_worker(self):

        self._ip, self._port = self._kwargs['ip-port'].split(':')
        self._port = int(self._port)
        self._timeout = self._kwargs.get('timeout', 1)

    def loop_worker(self):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(int(self._timeout))

        timeout = s.gettimeout()
        try:
            s.connect((self._ip, self._port))
            res = 1
        except (socket.timeout, socket.error):
            res = 0
        finally:
            s.close()
        self._log.info('status={status}'.format(port=self._port, ip=self._ip, status=res, timeout=timeout))
