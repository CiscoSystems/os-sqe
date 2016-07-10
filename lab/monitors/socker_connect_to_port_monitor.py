from lab.worker import Worker


class SocketConnectToPort(Worker):

    # noinspection PyAttributeOutsideInit
    def setup(self):
        import socket

        self._ip, self._port = self._kwargs['ip-port'].split(':')
        self._port = int(self._port)
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.settimeout(1)

    def loop(self):
        import socket

        try:
            self._s.connect((self._ip, self._port))
            res = 1
        except (socket.timeout, socket.error):
            res = 0
        finally:
            self._s.close()
        self._log.info('remote={ip}:{port} status={status}'.format(port=self._port, ip=self._ip, status=res))
