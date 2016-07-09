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
        duration = self._kwargs.get('duration')
        n_repeats = self._kwargs.get('n_repeats')
        if duration and n_repeats:
            raise ValueError('{}: specifies both duration and n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if duration is None and n_repeats is None:
            raise ValueError('{}: specifies neither duration no n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if n_repeats and n_repeats < 1:
            raise ValueError('{}: n_repeats should >=1'.format(self._kwargs))
        period = self._kwargs.get('period', 0)

        if delay:
            self._log.info('start by {0} secs...'.format(delay))
        time.sleep(delay)

        self._log.info('status=Start arguments={0}'.format(self._kwargs))
        accumulated_results = {'status': True, 'n_exceptions': 0}
        try:
            if duration:
                start_time = time.time()
                end_time = start_time + duration
                while time.time() < end_time:
                    results = self.loop()
                    accumulated_results.update(results)
                    time.sleep(period)
            elif n_repeats:
                for _ in range(n_repeats):
                    results = self.loop()
                    accumulated_results.update(results)
                    time.sleep(period)
        except:
            accumulated_results['n_exceptions'] += 1
            self._log.exception('EXCEPTION')

        return accumulated_results

    @abc.abstractmethod
    def setup(self, **kwargs):
        pass

    @abc.abstractmethod
    def loop(self):
        return {}
