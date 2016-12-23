import abc
import copy


class ParallelWorker(object):
    def __repr__(self):
        return u'worker={}'.format(type(self).__name__)

    def __init__(self,  cloud, lab, **kwargs):
        import validators

        self._results = {'name': str(self), 'exceptions': [], 'output': [], 'input': copy.deepcopy(kwargs)}
        del self._results['input']['_shared_dict']

        self._is_debug = False
        self._kwargs = kwargs
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
        self._run_once_when = self._kwargs.get('run_once_when', [])
        if not self._n_repeats and not self._run_while and not self._run_once_when and not self._duration:
            raise ValueError('Defined either run_while or n_repeats or run_once_when or duration')
        if (self._run_while or self._run_once_when) and not self._n_repeats:
            self._n_repeats = 1
        if self._run_while and self._n_repeats > 1:
            raise ValueError('n_repeats > 1 and run_while is defined! Either undefine run_while or set n_repeats=1 or even remove n_repeats')
        if self._duration and self._n_repeats:
            raise ValueError('{}: specified both duration and n_repeats. Decide which one you want to use.'.format(self._kwargs))
        if self._n_repeats and self._n_repeats < 1:
            raise ValueError('{}: n_repeats should >=1'.format(self._kwargs))

        # if self._duration:
        #     self._n_repeats = self._duration / self._period or 1

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
        import datetime
        import os
        import time
        from lab.logger import Logger

        # noinspection PyBroadException
        try:
            self._log = Logger(name=str(self))
            self._log.info(80 * '-')
            self._log.info('status=started parent_process={ppid} process_id={pid} arguments={args}'.format(args=self._kwargs, ppid=os.getppid(), pid=os.getpid()))

            self.set_flags()

            self.setup_worker()
            if self._delay:
                self._log.info('delay by {0} secs...'.format(self._delay))
                if not self._is_debug:
                    time.sleep(self._delay)

            if self._is_debug:  # don't actually run anything to check that infrastructure works
                self._results['output'].append(self.debug_output())
                return self._results

            if self._run_once_when:
                # Sleep for 1 second to let other workers to set flags.
                time.sleep(1)
                # Now all flags are set and we can check their values
                start_time = datetime.datetime.now()
                while not self.is_any_flag(flags=self._run_once_when) and (datetime.datetime.now() - start_time).seconds < 60 * 60 * 2:
                    # No one flag is True yet. Wait until at least one flag is true. Then start execution.
                    time.sleep(1)

                if self.is_any_flag(flags=self._run_once_when):
                    # Run once if any "run_once_when" flag meets expectations
                    loop_output = self.loop_worker()
                    if loop_output:
                        self._results['output'].append(loop_output)

            if self._run_while:
                self._log.debug("Entering run_while. [{0}]".format(self._kwargs))
                # Sleep for 1 second to let other workers to set flags.
                time.sleep(1)
                # Now all flags are set and we can check their values
                start_time = datetime.datetime.now()
                while not self.is_any_flag(flags=self._run_while) and (datetime.datetime.now() - start_time).seconds < 60 * 60 * 2:
                    # No one flag is True yet. Wait until at least one flag is true. Then start execution.
                    time.sleep(1)

                while self.is_any_flag(flags=self._run_while):
                    # Run while any "run_while" flag meets expectations
                    loop_output = self.loop_worker()
                    if loop_output:
                        self._results['output'].append(loop_output)
                    time.sleep(self._period)

            elif self._duration:
                self._log.debug("Entering duration. [{0}]".format(self._kwargs))
                start_time = datetime.datetime.now()
                while (datetime.datetime.now() - start_time).seconds < self._duration:
                    loop_output = self.loop_worker()
                    if loop_output:
                        self._results['output'].append(loop_output)
                    time.sleep(self._period)

            elif self._n_repeats:
                self._log.debug("Entering n_repeats. [{0}]".format(self._kwargs))
                for _ in range(self._n_repeats):
                    loop_output = self.loop_worker()
                    if loop_output:
                        self._results['output'].append(loop_output)
                    time.sleep(self._period)

        except Exception as ex:
            self._results['exceptions'].append(str(ex))
            self._log.exception('EXCEPTION')

        self.unset_flags()

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
        self._log.debug('Set flags [{0}]'.format(self._set))
        for flag in self._set:
            self._shared_dict[flag] = True

    def unset_flags(self):
        self._log.debug('Unset flags [{0}]'.format(self._set))
        for flag in self._set:
            self._shared_dict[flag] = False

    def is_any_flag(self, flags):
        true_strings = ('true', 'yes', 'on', 'buzz', 'working')
        self._log.debug("Watch flags [{0}]. Flags values [{1}]".format(flags, self._shared_dict))
        if type(flags) == list:
            return any([self._shared_dict[flag] for flag in flags])
        elif type(flags) == dict:
            return any([self._shared_dict[flag] == (value in true_strings) for flag, value in flags.items()])
        return False
