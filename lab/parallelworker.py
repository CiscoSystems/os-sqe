import abc
from lab.with_log import WithLogMixIn


class ParallelWorker(WithLogMixIn):
    STATUS_INIT = 'init'
    STATUS_DELAYED = 'delayed'
    STATUS_LOOPING = 'looping'
    STATUS_FINISHED = 'finished'

    def __repr__(self):
        return u'worker={}'.format(self._name)

    def __init__(self,  status_dict, args_dict):
        """ Executed before subprocesses start in the context of RunnerHA.execute()
        :param status_dict: dictionary defined as multiprocessing.Manager().dict() contains name: status pairs
        """
        import validators

        self._name = args_dict['name']
        self._status_dict = status_dict
        self.set_status(status=self.STATUS_INIT)
        self._kwargs = args_dict

        self._delay = self._kwargs.get('delay', 0)  # worker will be delayed by this seconds
        self._period = self._kwargs.get('period', 2)  # worker loop will be repeated with this period
        self._timeout = self._kwargs.get('timeout', 100)  # if operation will not successfully finished in that time, the worker will be forced to quit with exception

        self._n_repeats = self._kwargs.get('n_repeats')      # worker loop will be repeated n_repeats times
        self._loop_counter = 0                               # counts loops executed
        self._run_while = self._kwargs.get('run_while', [])  # worker will run till all these flags go False
        self._run_after = self._kwargs.get('run_after', [])  # worker will be delayed until all these flags will go False

        if type(self._run_while) is not list:
            self._run_while = [self._run_while]
        for x in self._run_while:
            if x not in self._status_dict.keys():
                raise ValueError('{}: run_while has "{}" which is invalid. Valid are {}'.format(self._yaml_path, x, self._status_dict.keys()))

        if type(self._run_after) is not list:
            self._run_after = [self._run_after]
        for x in self._run_after:
            if x not in self._status_dict:
                raise ValueError('{}: run_after has "{}" which is invalid. Valid are {}'.format(self._yaml_path, x, self._status_dict.keys()))

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
        return self._kwargs['lab']

    def get_cloud(self):
        return self._kwargs['cloud']

    def get_mgmt(self):
        return self.get_lab().get_director()

    def is_debug(self):
        return self._kwargs['is-debug']

    @property
    def is_noclean(self):
        return self._kwargs['is-noclean']

    @property
    def _yaml_path(self):
        return self._kwargs['task-yaml-path']

    def set_status(self, status):
        self._status_dict[self._name] = status

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

    def is_ready_to_finish(self):
        if self._run_while:
            return all([self._status_dict[x] == 'finished' for x in self._run_while])
        else:
            if self._n_repeats == 0:
                return True
            else:
                self._n_repeats -= 1
                return False

    def delay(self):
        import time

        self.set_status(status=self.STATUS_DELAYED)

        time_passed = 0
        if self._run_after:
            self.log('delay till {} are false'.format(self._run_after))
            while not all([self._status_dict[x] for x in self._run_while]):  # first wait for all run_after workers go True
                time.sleep(1)
                time_passed += 1
                if time_passed == self._timeout:
                    raise RuntimeError('Waiting for {} to be all True exceeded {} secs'.format(self._run_after, self._timeout))
            while not all([not self._status_dict[x] for x in self._run_while]):  # now wait to all run_after workers go False
                time.sleep(1)
                time_passed += 1
                if time_passed == self._timeout:
                    raise RuntimeError('Waiting for {} to be all False exceeded {} secs'.format(self._run_after, self._timeout))

        if self._delay:
            self.log('delay by {} secs...'.format(self._delay))
            if not self.is_debug():
                time.sleep(self._delay)

    def start_worker(self):
        """This code is executed once when subprocess starts. This is the only entry point to the worker."""
        import os
        import time

        worker_parameters = 'ppid={} pid={} {}'.format(os.getppid(), os.getpid(), self.check_config())
        self.log(worker_parameters)
        time.sleep(1)

        exceptions = []
        try:
            self.delay()

            if not self.is_debug():
                self.setup_worker()

            self.set_status(status=self.STATUS_LOOPING)

            while not self.is_ready_to_finish():
                self.log('Loop number {}...'.format(self._loop_counter))
                self.loop_worker() if not self.is_debug() else self.debug_output()
                self._loop_counter += 1
                time.sleep(self._period)

            self.log('FINISHED')
        except Exception as ex:
            exceptions.append(str(ex))
            self.log(message='EXCEPTION', level='exception')
        finally:
            self.set_status(status=self.STATUS_FINISHED)
            if not self.is_debug():
                self.teardown_worker()
            return {'worker name': self._name, 'exceptions': exceptions, 'params': worker_parameters}

    def debug_output(self):
        return '{} loop {} ok'.format(self._name, self._loop_counter)
