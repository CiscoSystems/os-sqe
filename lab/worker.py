import abc


class Worker(object):
    def __init__(self,  cloud, lab, **kwargs):
        import validators

        self._is_debug = False
        self._kwargs = kwargs
        self._cloud = cloud
        self._lab = lab
        self._ip = kwargs.get('ip')
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

    # noinspection PyBroadException
    # noinspection PyAttributeOutsideInit
    def start_worker(self):
        import time
        from lab.logger import Logger

        self._log = Logger(name=str(self))
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
            self._log.info('delay by {0} secs...'.format(delay))
        if not self._is_debug:
            time.sleep(delay)

        self._log.info('status=started arguments={0}'.format(self._kwargs))
        results = {'name': str(self), 'n_exceptions': 0, 'is_success': True}
        if self._is_debug:
            return results  # don't actually run anything to check that infrastructure works
        try:
            if duration:
                start_time = time.time()
                end_time = start_time + duration
                while time.time() < end_time:
                    self.loop_worker()
                    time.sleep(period)
            elif n_repeats:
                for _ in range(n_repeats):
                    self.loop_worker()
                    time.sleep(period)
        except:
            results['n_exceptions'] += 1
            results['is_success'] = False
            self._log.exception('EXCEPTION')

        return results

    @abc.abstractmethod
    def setup_worker(self, **kwargs):
        pass

    @abc.abstractmethod
    def loop_worker(self):
        return {}
