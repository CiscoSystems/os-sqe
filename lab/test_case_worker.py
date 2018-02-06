import abc
from lab.with_log import WithLogMixIn


class TestCaseWorker(WithLogMixIn):
    STATUS_CREATED = 'created'
    STATUS_SETUP = 'setup'
    STATUS_DELAYED = 'delayed'
    STATUS_LOOPING = 'looping'
    STATUS_FINISHED = 'finished'

    ARG_DELAY = 'delay'
    ARG_RUN = 'run'
    ARG_PERIOD = 'pause'
    ARG_TIMEOUT = 'timeout'

    def __repr__(self):
        return u'TCW={}.{}'.format(self.test_case.path.split('-')[0], self.name)

    def __init__(self, test_case, args_dict):
        """ Executed before subprocesses start in the context of RunnerHA.execute()
        :param args_dict: dictionry with custom worker arguments, they are checked in check_config()
        """
        self.test_case = test_case
        self.name = args_dict.pop('name')
        self.worker_data = ''                                                  # might be set to some arbotrary object in worker_loop()
        self.is_failed = False                                                 # might be set by self.fail()
        self.exceptions = []                                                   # any exceptions will be collected here
        self.status_dict = None                                                # will be set just before running multiprocessing.Pool.map() to multiprocessing.Manager().dict()
        self.cloud = test_case.cloud
        self.args = {}                                                         # all arguments will be kept in this dict
        self.loop_counter = 0                                                  # counts loops executed

        args_dict.pop('class')
        self.required_properties = set([getattr(self, x) for x in dir(self) if x.startswith('ARG_')])
        assert self.required_properties.issubset(dir(self)), '{}: please define method(s) decorated with @property {}'.format(self, self.required_properties - set(dir(self)))
        for x in sorted(self.required_properties):
            assert x in args_dict, '{}: no argument "{}"'.format(self, x)
            self.args[x] = args_dict.pop(x)
        assert len(args_dict) == 0, '{}: argument dict contains not known key(s): {}'.format(self, args_dict)
        if type(self.run) is not list:
            assert type(self.run) is int and self.run > 0
        if type(self.delay) is not list:
            assert type(self.delay) is int and self.delay >= 0, '{}: wrong delay "{}". should be list of names or int'.format(self, self.delay)

        self.check_arguments()

    @property
    def description(self):
        return ' '.join(['{}={}'.format(x[0], x[1]) for x in self.args.items()])

    @property
    def delay(self):  # delay: 3 means delay by 3 secs after common start, delay: [name1, name2] means delay until workers name1, name2 go to self.STATUS_FINISHED
        return self.args[self.ARG_DELAY]

    @property
    def run(self):  # run: 3 means repeat 3 times, run: [name1, name2] means run until workers name1, name2 go to self.STATUS_FINISHED
        return self.args[self.ARG_RUN]

    @property
    def timeout(self):  # if operation will not successfully finished in that time, the worker will be forced to quit with exception
        return self.args[self.ARG_TIMEOUT]

    @property
    def pause(self):  # wait this time at the end of each loop
        return self.args[self.ARG_PERIOD]

    @property
    def pod(self):
        return self.cloud.pod

    @property
    def mgm(self):
        return self.pod.mgm

    def set_status(self, status):
        self.status_dict[self.name] = status

    @abc.abstractmethod
    def check_arguments(self):
        raise NotImplementedError(self, 'check_arguments')

    @abc.abstractmethod
    def setup_worker(self):
        raise NotImplementedError(self)

    @abc.abstractmethod
    def loop_worker(self):
        raise NotImplementedError(self)

    def teardown_worker(self):
        pass

    def is_ready_to_finish(self):
        if type(self.run) is list:
            return all([self.status_dict[x] == self.STATUS_FINISHED for x in self.run])
        else:
            return self.run == self.loop_counter

    def delay_execution(self):
        import time

        self.set_status(status=self.STATUS_DELAYED)

        time_passed = 0
        if type(self.delay) is list:
            self.log('delay while {} not yet {}'.format(self.delay, self.STATUS_FINISHED))
            while all([self.status_dict[x] != self.STATUS_FINISHED for x in self.delay]):
                time.sleep(1)
                time_passed += 1
                if time_passed == self.timeout:
                    raise RuntimeError('Waiting for {} to be all False exceeded {} secs'.format(self.delay, self.timeout))
            self.log('{}=finish, worker now active'.format(self.delay))
        else:
            self.log('delay by {} secs...'.format(self.delay))
            time.sleep(self.delay)

    def start_worker_parallel(self):
        """This code is executed once when subprocess starts. This is the only entry point to the worker loop."""
        import os
        import time
        import sys

        worker_parameters = 'ppid={} pid={} {}'.format(os.getppid(), os.getpid(), self.description)
        self.log(worker_parameters)
        time.sleep(1)

        try:
            self.delay_execution()

            self.set_status(status=self.STATUS_LOOPING)

            while not self.is_ready_to_finish():
                self.log(' loop={} of total={} {} ...'.format(self.loop_counter, self.run, self.status_dict))

                if not self.test_case.is_debug:
                    self.loop_worker()

                if self.pause > 0:
                    self.log(' loop={} pausing={} sec ...'.format(self.loop_counter, self.pause ))
                    time.sleep(1 if self.test_case.is_debug else self.pause)

                self.loop_counter += 1

            self.log('status=finish after loop={} of total={} with data={}, {}'.format(self.loop_counter, self.run, self.worker_data, self.status_dict))
        except Exception as ex:
            frame = sys.exc_traceback
            while frame.tb_next:
                frame = frame.tb_next
            self.exceptions.append(str(ex).replace('\\', '') + ' ' + frame.tb_frame.f_code.co_filename + ':' + str(frame.tb_lineno))
            self.log_exception()
        finally:
            time.sleep(1)  # sleep to align log output
            self.set_status(status=self.STATUS_FINISHED)
            return self

    def fail(self, message, is_stop_running):
        self.is_failed = True
        if is_stop_running:
            raise RuntimeError(str(message))
