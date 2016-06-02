import abc


class Worker(object):
    def __init__(self,  cloud, **kwargs):
        import validators

        self._kwargs = kwargs
        self._cloud = cloud
        self._ip = kwargs.get('ip')
        if self._ip:
            if validators.ipv4(self._ip):
                try:
                    self._username, self._password = kwargs['username'], kwargs['password']
                except KeyError:
                    raise ValueError('"username" and/or "password"  are not provided'.format())
            else:
                raise ValueError('Provided invalid ip address: "{0}"'.format(self._ip))

    # noinspection PyBroadException
    # noinspection PyAttributeOutsideInit
    def start(self):
        import time
        from lab.logger import create_logger

        self._log = create_logger(name=str(type(self)))
        delay = self._kwargs.get('delay', 0)
        duration = self._kwargs.get('duration', 3)
        period = self._kwargs.get('period', 0)

        if delay:
            self._log.info('start by {0} secs...'.format(delay))
        time.sleep(delay)

        self._log.info('status=Start arguments={0}'.format(self._kwargs))
        start_time = time.time()
        end_time = start_time + duration
        try:
            while time.time() < end_time:
                self.loop()
                time.sleep(period)
        except:
            self._log.exception('EXCEPTION')

    @abc.abstractmethod
    def setup(self, **kwargs):
        pass

    @abc.abstractmethod
    def loop(self):
        pass
