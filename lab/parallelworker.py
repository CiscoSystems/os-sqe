import abc
from lab.with_log import WithLogMixIn


class ParallelWorker(WithLogMixIn):
    STATUS_INITIALIZED = 'init'
    STATUS_DELAYED = 'delayed'
    STATUS_LOOPING = 'looping'
    STATUS_FINISHED = 'finished'

    def __repr__(self):
        return u'test={} worker={}'.format(self.test_cfg_path, self.name)

    def __init__(self, args_dict):
        """ Executed before subprocesses start in the context of RunnerHA.execute()
        :param args_dict: dictionry with custom worker arguments, they are checked in check_config()
        """
        self.name = args_dict.pop('name')
        self.test_cfg_path = args_dict.pop('test_cfg_path')
        self.status_dict = None

        self.delay = args_dict.pop('delay', 0)  # worker will be delayed by this seconds
        self.period = args_dict.pop('period', 2)  # worker loop will be repeated with this period
        self.timeout = args_dict.pop('timeout', 100)  # if operation will not successfully finished in that time, the worker will be forced to quit with exception

        self.n_repeats = args_dict.pop('n_repeats', -1)      # worker loop will be repeated n_repeats times
        self.loop_counter = 0                                # counts loops executed
        self.run_while = args_dict.pop('run_while', [])  # worker will run till all these flags go False
        self.run_after = args_dict.pop('run_after', [])  # worker will be delayed until all these flags will go False

        self.cloud = None
        self.is_noclean = args_dict.pop('is_noclean')
        self._kwargs = args_dict

    @property
    def pod(self):
        return self.cloud.pod

    @property
    def mgmt(self):
        return self.pod.mgmt

    def set_status(self, status):
        self.status_dict[self.name] = status

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
        if self.run_while:
            return all([self.status_dict[x] == 'finished' for x in self.run_while])
        else:
            if self.n_repeats == 0:
                return True
            else:
                self.n_repeats -= 1
                return False

    def delay_execution(self):
        import time

        self.set_status(status=self.STATUS_DELAYED)

        time_passed = 0
        if self.run_after:
            self.log('delay till {} are false'.format(self.run_after))
            while not all([self.status_dict[x] for x in self.run_while]):  # first wait for all run_after workers go True
                time.sleep(1)
                time_passed += 1
                if time_passed == self.timeout:
                    raise RuntimeError('Waiting for {} to be all True exceeded {} secs'.format(self.run_after, self.timeout))
            while not all([not self.status_dict[x] for x in self.run_while]):  # now wait to all run_after workers go False
                time.sleep(1)
                time_passed += 1
                if time_passed == self.timeout:
                    raise RuntimeError('Waiting for {} to be all False exceeded {} secs'.format(self.run_after, self.timeout))

        if self.delay:
            self.log('delay by {} secs...'.format(self.delay))
            time.sleep(self.delay)

    def start_worker_parallel(self):
        """This code is executed once when subprocess starts. This is the only entry point to the worker loop."""
        import os
        import time

        worker_parameters = 'ppid={} pid={} {}'.format(os.getppid(), os.getpid(), self.check_config())
        self.log(worker_parameters)
        time.sleep(1)

        exceptions = []
        try:
            self.delay_execution()

            self.set_status(status=self.STATUS_LOOPING)

            while not self.is_ready_to_finish():
                self.log('Loop number {}...'.format(self.loop_counter))
                self.loop_worker()
                self.loop_counter += 1
                time.sleep(self.period)

            self.log('FINISHED')
        except Exception as ex:
            exceptions.append(str(ex))
            self.log_exception()
        finally:
            time.sleep(1)  # sleep to align log output
            self.set_status(status=self.STATUS_FINISHED)
            return {'worker name': self.name, 'exceptions': exceptions, 'params': worker_parameters}
