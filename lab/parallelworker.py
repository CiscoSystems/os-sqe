import abc
from lab.with_log import WithLogMixIn


class ParallelWorker(WithLogMixIn):
    def __repr__(self):
        return u'worker={}'.format(type(self).__name__)

    def __init__(self,  shared_dict, name):
        """ Executed before subprocesses start in the context of RunnerHA.execute()
        :param shared_dict: dictionary defined as multiprocessing.Manager().dict()
        """
        import validators

        self._run_params = {}

        self._shared_dict = shared_dict
        self._kwargs = self._shared_dict[name]
        self._kwargs['status'] = 'init'

        self._results = {'name': str(self), 'exceptions': [], 'output': [], 'input': self._kwargs}

        self._delay = self._kwargs.get('delay', 0)  # worker will be delayed by this seconds
        self._period = self._kwargs.get('period', 2)  # worker loop will be repeated with this period
        self._timeout = self._kwargs.get('timeout', 3600)  # if flags don't be False in that time, the worker will be forced to quit with exception

        self._n_repeats = self._kwargs.get('n_repeats')      # worker loop will be repeated n_repeats times
        self._loop_counter = 0                         # counts loops executed
        self._run_while = self._kwargs.get('run_while', [])  # worker will run till all these flags go False
        self._run_after = self._kwargs.get('run_after', [])  # worker will be delayed until all these flags will go False

        if type(self._run_while) is not list:
            self._run_while = [self._run_while]
        for x in self._run_while:
            if x not in self._shared_dict.keys():
                raise ValueError('{}: run_while has "{}" which is invalid. Valid are {}'.format(self._kwargs['yaml_path'], x, self._shared_dict.keys()))

        if type(self._run_after) is not list:
            self._run_after = [self._run_after]
        for x in self._run_after:
            if x not in self._shared_dict.keys():
                raise ValueError('{}: run_after has "{}" which is invalid. Valid are {}'.format(self._kwargs['yaml_path'], x, self._shared_dict.keys()))

        if self._run_while:
            if any([self._run_after, self._n_repeats]):
                raise ValueError('run_while can not co-exists with either of n_repeats and run_after in {}'.format(self._kwargs))
        else:
            if self._n_repeats is None or self._n_repeats < 1:
                raise ValueError('{} section {}: please define n_repeats >=1'.format(self._yaml_path, self._kwargs['class']))

        self._ip = self._kwargs.get('ip')
        if self._ip:
            if validators.ipv4(self._ip):
                try:
                    self._username, self._password = self._kwargs['username'], self._kwargs['password']
                except KeyError:
                    raise ValueError('"username" and/or "password"  are not provided'.format())
            else:
                raise ValueError('Provided invalid ip address: "{0}"'.format(self._ip))

        try:
            self.check_config()
        except KeyError as ex:
            raise ValueError('{} section {}: no required parameter "{}"'.format(self._yaml_path, self, ex))

    def get_lab(self):
        return self._shared_dict['lab']

    def get_cloud(self):
        return self._shared_dict['cloud']

    def get_mgmt(self):
        return self.get_lab().get_director()

    def is_debug(self):
        return self._shared_dict['is-debug']

    @property
    def _yaml_path(self):
        return self._shared_dict['yaml-path']

    def set_status(self, status):
        self._kwargs['status'] = status

    @abc.abstractmethod
    def check_config(self):
        raise NotImplementedError(self)

    @abc.abstractmethod
    def setup_worker(self):
        raise NotImplementedError(self)

    @abc.abstractmethod
    def loop_worker(self):
        raise NotImplementedError(self)

    def teardown_worker(self):
        pass

    def is_still_loop(self):
        if self._run_while:
            return all([self._shared_dict[x]['status'] == 'running' for x in self._run_while])
        elif self._n_repeats:
            self._n_repeats -= 1
            return True
        else:
            return False

    def delay(self):
        import time

        if self._delay:
            self.log('delay by {} secs...'.format(self._delay))
            if not self.is_debug():
                time.sleep(self._delay)

        time_passed = 0
        if self._run_after:
            self.log('delay till {} are false'.format(self._run_after))
            while not all([self._shared_dict[x] for x in self._run_while]):  # first wait for all run_after workers go True
                time.sleep(1)
                time_passed += 1
                if time_passed == self._timeout:
                    raise RuntimeError('Waiting for {} to be all True exceeded {} secs'.format(self._run_after, self._timeout))
            while not all([not self._shared_dict[x] for x in self._run_while]):  # now wait to all run_after workers go False
                time.sleep(1)
                time_passed += 1
                if time_passed == self._timeout:
                    raise RuntimeError('Waiting for {} to be all False exceeded {} secs'.format(self._run_after, self._timeout))

    def start_worker(self):
        """This code is executed once when subprocess starts. This is the only entry point to the worker."""
        import os
        import time

        self.log('status=started ppid={} pid={} arguments={}'.format(os.getppid(), os.getpid(), self._results['input']))

        self.set_status(status='setting')

        try:
            self.delay()

            if not self.is_debug():
                self.setup_worker()
            self.set_status(status='looping')

            while self.is_still_loop():
                self.log('Loop number {}...'.format(self._loop_counter))
                loop_output = self.loop_worker() if not self.is_debug() else self.debug_output()
                self._loop_counter += 1
                self._results['output'].append(loop_output)
                time.sleep(self._period)

            if not self.is_debug():
                self.teardown_worker()
            self.log('FINISHED')
        except Exception as ex:
            self._results['exceptions'].append(str(ex))
            self.log(message='EXCEPTION', level='exception')
        finally:
            self.set_status(status='finished')
        return self._results

    @staticmethod
    def debug_output():
        return 'Generic debug output'