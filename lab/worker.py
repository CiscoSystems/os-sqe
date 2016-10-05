import abc


class Worker(object):
    def __init__(self,  cloud, lab, **kwargs):
        import validators

        self._is_debug = False
        self._kwargs = kwargs
        self._cloud = cloud
        self._lab = lab
        self._log = None
        self._ip = kwargs.get('ip')
        self._delay = self._kwargs.get('delay', 0)
        self._period = self._kwargs.get('period', 0)
        self._duration = self._kwargs.get('duration')
        self._n_repeats = self._kwargs.get('n_repeats')
        if self._duration and self._n_repeats:
            raise ValueError('{}: specifies both duration and n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if self._duration is None and self._n_repeats is None:
            raise ValueError('{}: specifies neither duration no n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if self._n_repeats and self._n_repeats < 1:
            raise ValueError('{}: n_repeats should >=1'.format(self._kwargs))
        if self._ip:
            if validators.ipv4(self._ip):
                try:
                    self._username, self._password = kwargs['username'], kwargs['password']
                except KeyError:
                    raise ValueError('"username" and/or "password"  are not provided'.format())
            else:
                raise ValueError('Provided invalid ip address: "{0}"'.format(self._ip))

    def set_is_debug(self, is_debug):
        self._is_debug = is_debug

    def start_worker(self):
        import time
        from lab.logger import Logger

        results = {'name': str(self), 'exceptions': []}

        # noinspection PyBroadException
        try:
            self._log = Logger(name=str(self))
            self._log.info('status=started arguments={0}'.format(self._kwargs))
            self.setup_worker()
            if self._delay:
                self._log.info('delay by {0} secs...'.format(self._delay))
            if not self._is_debug:
                time.sleep(self._delay)

            if self._is_debug:
                return results  # don't actually run anything to check that infrastructure works
            if self._duration:
                start_time = time.time()
                end_time = start_time + self._duration
                while time.time() < end_time:
                    self.loop_worker()
                    time.sleep(self._period)
            elif self._n_repeats:
                for _ in range(self._n_repeats):
                    self.loop_worker()
                    time.sleep(self._period)
        except Exception as ex:
            results['exceptions'].append(ex)
            self._log.exception('EXCEPTION')

        self._log.info('status=finished arguments={0}'.format(self._kwargs))
        return results

    @abc.abstractmethod
    def setup_worker(self, **kwargs):
        pass

    @abc.abstractmethod
    def loop_worker(self):
        return {}
