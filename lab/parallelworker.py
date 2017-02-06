import abc
from lab.with_log import WithLogMixIn


class ParallelWorker(WithLogMixIn):
    def __repr__(self):
        return u'worker={}'.format(type(self).__name__)

    def __init__(self,  cloud, lab, shared_dict, is_debug, **kwargs):
        """ Executed before subprocesses start in the context of RunnerHA.execute()
        :param cloud: instance of Cloud class
        :param lab: instance of Laboratory class
        :param shared_dict: dictionary defined as multiprocessing.Manager().dict()
        :param is_debug: id true don't run actual cloud and lab operations, used as a way to debug parallel infrastructure
        :param kwargs: dictionary with parameters as defined in worker section of yaml file
        """
        import validators

        self._kwargs = kwargs
        self._cloud = cloud
        self._lab = lab
        self._build_node = cloud.get_mediator()

        self._shared_dict = shared_dict
        self._this_worker_in_shared_dict = type(self).__name__
        self._results = {'name': str(self), 'exceptions': [], 'output': [], 'input': kwargs}

        self._is_debug = is_debug
        self._delay = kwargs.get('delay', 0)  # worker will be delayed by this seconds
        self._period = kwargs.get('period', 2)  # worker loop will be repeated with this period
        self._timeout = kwargs.get('timeout', 3600)  # if flags don't be False in that time, the worker will be forced to quit with exception

        self._n_repeats = kwargs.get('n_repeats')      # worker loop will be repeated n_repeats times
        self._loop_counter = 0                         # counts loops executed
        self._run_while = kwargs.get('run_while', [])  # worker will run till all these flags go False
        self._run_after = kwargs.get('run_after', [])  # worker will be delayed until all these flags will go False
        self.check_arguments(**kwargs)  # this call might change n_repeats

        if type(self._run_while) is not list:
            self._run_while = [self._run_while]

        if type(self._run_after) is not list:
            self._run_after = [self._run_after]

        if self._run_while:
            if any([self._run_after, self._n_repeats]):
                raise ValueError('run_while can not co-exists with either of n_repeats and run_after in {}'.format(kwargs))
        else:
            if self._n_repeats is None or self._n_repeats < 1:
                raise ValueError('Please define n_repeats >=1 in {}'.format(kwargs))

        self._ip = kwargs.get('ip')
        if self._ip:
            if validators.ipv4(self._ip):
                try:
                    self._username, self._password = kwargs['username'], kwargs['password']
                except KeyError:
                    raise ValueError('"username" and/or "password"  are not provided'.format())
            else:
                raise ValueError('Provided invalid ip address: "{0}"'.format(self._ip))

    def get_lab(self):
        return self._lab

    def get_cloud(self):
        return self._cloud

    @abc.abstractmethod
    def check_arguments(self, **kwargs):
        raise NotImplementedError(self)

    @abc.abstractmethod
    def setup_worker(self, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def loop_worker(self, **kwargs):
        raise NotImplementedError

    def teardown_worker(self):
        pass

    def is_still_loop(self):
        if self._run_while:
            return all(self._run_while)
        elif self._n_repeats:
            self._n_repeats -= 1
            return True
        else:
            return True

    def delay(self):
        import time

        if self._delay:
            self.log('delay by {} secs...'.format(self._delay))
            if not self._is_debug:
                time.sleep(self._delay)

        time_passed = 0
        if self._run_after:
            self.log('delay till {} are false'.format(self._run_after))
            while not all(self._run_after):  # wait for all other workers set their flags to true
                time.sleep(1)
                time_passed += 1
                if time_passed == self._timeout:
                    raise RuntimeError('Waiting for {} to be all True exceeded {} secs'.format(self._run_after, self._timeout))
            while all(self._run_after):
                time.sleep(1)
                time_passed += 1
                if time_passed == self._timeout:
                    raise RuntimeError('Waiting for {} to be all False exceeded {} secs'.format(self._run_after, self._timeout))

    def start_worker(self):
        """This code is executed once when subprocess starts. This is the only entry point to the worker."""
        import os
        import time

        self.log('status=started ppid={} pid={} arguments={}'.format(os.getppid(), os.getpid(), self._results['input']))

        self._shared_dict[self._this_worker_in_shared_dict] = True

        try:
            self.delay()

            self.setup_worker()

            while self.is_still_loop():
                self.log('Loop...')
                loop_output = self.loop_worker() if not self._is_debug else self.debug_output()
                self._loop_counter += 1
                self._results['output'].append(loop_output)
                time.sleep(self._period)

        except Exception as ex:
            self._results['exceptions'].append(str(ex))
            self.log(message='EXCEPTION', level='exception')

        self.teardown_worker()

        self._shared_dict[self._this_worker_in_shared_dict] = False

        return self._results

    @staticmethod
    def debug_output():
        return 'Generic debug output'
