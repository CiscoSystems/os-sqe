import abc


class ParallelWorker(object):
    def __init__(self,  cloud, lab, **kwargs):
        import validators

        self._is_debug = False
        self._kwargs = kwargs
        self._results = {'name': str(self), 'exceptions': [], 'output': [], 'input': kwargs}
        self._cloud = cloud
        self._lab = lab
        self._log = None
        self._ip = kwargs.get('ip')
        self._delay = self._kwargs.get('delay', 0)
        self._period = self._kwargs.get('period', 2)
        self._duration = self._kwargs.get('duration')
        self._n_repeats = self._kwargs.get('n_repeats')
        if self._duration and self._n_repeats:
            raise ValueError('{}: specifies both duration and n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if self._duration is None and self._n_repeats is None:
            raise ValueError('{}: specifies neither duration no n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if self._n_repeats and self._n_repeats < 1:
            raise ValueError('{}: n_repeats should >=1'.format(self._kwargs))

        if self._duration:
            self._n_repeats = self._duration / self._period or 1

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

        # noinspection PyBroadException
        try:
            self._log = Logger(name=str(self))
            self._log.info('status=started arguments={}'.format(self._kwargs))
            if self._is_debug:  # don't actually run anything to check that infrastructure works
                self._results['output'].append(self.debug_output())
                return self._results
            self.setup_worker()
            if self._delay:
                self._log.info('delay by {0} secs...'.format(self._delay))
            if not self._is_debug:
                time.sleep(self._delay)

            for _ in range(self._n_repeats):
                loop_output = self.loop_worker()
                if loop_output:
                    self._results['output'].append(loop_output)
                time.sleep(self._period)
        except Exception as ex:
            self._results['exceptions'].append(ex)
            self._log.exception('EXCEPTION')

        self._log.info('status=finished arguments={0}'.format(self._kwargs))
        return self._results

    @abc.abstractmethod
    def setup_worker(self, **kwargs):
        raise NotImplemented

    @abc.abstractmethod
    def loop_worker(self):
        raise NotImplemented

    @staticmethod
    def debug_output():
        return 'Generic debug output'
