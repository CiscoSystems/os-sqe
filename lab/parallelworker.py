import abc


class ParallelWorker(object):
    def __repr__(self):
        return u'worker={}'.format(type(self).__name__)

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
        self._shared_dict = self._kwargs.get('_shared_dict')
        self._set = self._kwargs.get('set', [])
        self._run_while = self._kwargs.get('run_while', [])
        if not self._n_repeats and not self._run_while:
            raise ValueError('Defined either run_while or n_repeats')
        if self._run_while and not self._n_repeats:
            self._n_repeats = 1
        if self._run_while and self._n_repeats > 1:
            raise ValueError('n_repeats > 1 and run_while is defined! Either undefine run_while or set n_repeats=1 or even remove n_repeats')
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
            self._log.info(80 * '-')
            self._log.info('status=started arguments={}'.format(self._kwargs))
            if self._is_debug:  # don't actually run anything to check that infrastructure works
                self._results['output'].append(self.debug_output())
                return self._results

            self.set_flags()
            self.setup_worker()
            if self._delay:
                self._log.info('delay by {0} secs...'.format(self._delay))
            if not self._is_debug:
                time.sleep(self._delay)

            if self._run_while:
                # Sleep for 1 second to let other workers to set flags.
                time.sleep(1)
                # Now all flags are set and we can check their values
                while self.is_any_flag():
                    loop_output = self.loop_worker()
                    if loop_output:
                        self._results['output'].append(loop_output)
                    time.sleep(self._period)
            elif self._n_repeats:
                for _ in range(self._n_repeats):
                    loop_output = self.loop_worker()
                    if loop_output:
                        self._results['output'].append(loop_output)
                    time.sleep(self._period)
            self.unset_flags()
        except Exception as ex:
            self._results['exceptions'].append(str(ex))
            self._log.exception('EXCEPTION')

        self._log.info('status=finished arguments={0}'.format(self._kwargs))
        self.teardown_worker()
        self._log.info(80 * '-')
        return self._results

    @abc.abstractmethod
    def setup_worker(self, **kwargs):
        raise NotImplemented

    @abc.abstractmethod
    def loop_worker(self):
        raise NotImplemented

    def teardown_worker(self):
        pass

    @staticmethod
    def debug_output():
        return 'Generic debug output'

    def set_flags(self):
        for flag in self._set:
            self._shared_dict[flag] = True

    def unset_flags(self):
        for flag in self._set:
            self._shared_dict[flag] = False

    def is_any_flag(self, value=True):
        return any([self._shared_dict[flag] == value for flag in self._run_while])
