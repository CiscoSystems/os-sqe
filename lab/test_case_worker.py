import abc
from lab.with_log import WithLogMixIn


class TestCaseWorker(WithLogMixIn):
    STATUS_CREATED = 'created'
    STATUS_SETUP_RUNING = 'status=NonParallelSetupRunning'
    STATUS_SETUP_FINISHED = 'status=NonParallelSetupFinished ' + 47 * '-'
    STATUS_DELAYED = 'delayed'
    STATUS_LOOPING = 'looping'
    STATUS_FINISHED = 'finished'
    STATUS_FAILED = 'status=FAILED message='
    STATUS_PASSED = 'status=PASSED message='

    STATUS_IMAGE_CREATING = 'status=ImageCreating'
    STATUS_IMAGE_CREATED = 'status=ImageCreated'

    STATUS_FLAVOR_CREATING = 'status=FlavorCreating'
    STATUS_FLAVOR_CREATED = 'status=FlavorCreated'

    STATUS_KEYPAIR_CREATING = 'status=KeyPairCreating'
    STATUS_KEYPAIR_CREATED = 'status=KeyPairCreated'

    STATUS_SERVER_CREATING = 'status=ServerCreating'
    STATUS_SERVER_CREATED = 'status=ServerCreated'
    STATUS_SERVER_SNAPSHOTING = 'status=ServerSnapshoting'
    STATUS_SERVER_SNAPSHOTED = 'status=ServerSnapshoted'

    STATUS_OS_CLEANING = 'status=OpenstackCleaning'
    STATUS_OS_CLEANED = 'status=OpenstackCleaned'

    ARG_MANDATORY_DELAY = 'delay'
    ARG_MANDATORY_RUN = 'run'
    ARG_OPTIONAL_PAUSE_AT_START = 'pause_at_start'
    ARG_OPTIONAL_PAUSE_AT_END = 'pause_at_end'
    ARG_OPTIONAL_TIMEOUT = 'timeout'

    def __repr__(self):
        return u'TCW={}.{}'.format(self.test_case.path.split('-')[0], self.name)

    def __init__(self, test_case, args_dict):
        """ Executed before subprocesses start in the context of RunnerHA.execute()
        :param args_dict: dictionry with custom worker arguments, they are checked in check_config()
        """
        self.test_case = test_case
        self.name = args_dict.pop('name')
        self.successes = []                                                    # succeses will be collected here in self.passed()
        self.failures = []                                                     # failures (problems in soft under test) will be collected here in self.failed()
        self.errors = []                                                       # errors (problems in this code) will be collected here self.start_worker_parallel()
        self.status_dict = None                                                # will be set just before running multiprocessing.Pool.map() to multiprocessing.Manager().dict()
        self.cloud = test_case.cloud
        self.args = {}                                                         # all arguments will be kept in this dict
        self.loop_counter = 0                                                  # counts loops executed

        args_dict.pop('class')

        all_arg_names = set([x for x in dir(self) if x.startswith('ARG')])
        correct_names = set([x for x in all_arg_names if x.startswith('ARG_MANDATORY_') or x.startswith('ARG_OPTIONAL_')])
        assert len(all_arg_names - correct_names) == 0, '{}: has wrong argument definitions: {}, all must start with either ARG_MANDATORY_ or ARG_OPTIONAL_'.format(self.__class__, all_arg_names - correct_names)

        optional_arguments = set([getattr(self, x) for x in correct_names if x.startswith('ARG_OPTIONAL_')])
        required_arguments = set([getattr(self, x) for x in correct_names if x.startswith('ARG_MANDATORY_')])
        all_arguments = optional_arguments ^ required_arguments
        assert all_arguments.issubset(dir(self)), '{}: please define method(s) decorated with @property {}'.format(self.__class__, all_arguments - set(dir(self)))
        for x in sorted(required_arguments):
            assert x in args_dict, '{}: no mandatory argument "{}"'.format(self, x)
            self.args[x] = args_dict.pop(x)
        for x in sorted(optional_arguments):
            if x in args_dict:
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
        return self.args[self.ARG_MANDATORY_DELAY]

    @property
    def run(self):  # run: 3 means repeat 3 times, run: [name1, name2] means run until workers name1, name2 go to self.STATUS_FINISHED
        return self.args[self.ARG_MANDATORY_RUN]

    @property
    def timeout(self):  # if operation will not successfully finished in that time, the worker will be forced to quit with exception
        return self.args.get(self.ARG_OPTIONAL_TIMEOUT, 1000)

    @property
    def pause_at_start(self):  # wait this time at the start of each loop
        return self.args.get(self.ARG_OPTIONAL_PAUSE_AT_START, 0)

    @property
    def pause_at_end(self):  # wait this time at the end of each loop
        return self.args.get(self.ARG_OPTIONAL_PAUSE_AT_END, 0)

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
            self.log('status=delayed until other={} finish'.format(self.delay, self.STATUS_FINISHED))
            while all([self.status_dict[x] != self.STATUS_FINISHED for x in self.delay]):
                time.sleep(1)
                time_passed += 1
                if time_passed == self.timeout:
                    raise RuntimeError('{} not finished in {} secs'.format(self.delay, self.timeout))
            self.log('status=active since other={} finished'.format(self.delay))
        else:
            self.log('status=delayed for time={} secs...'.format(self.delay))
            time.sleep(1 if self.test_case.is_debug else self.delay)

    def start_worker_parallel(self):
        """This code is executed once when subprocess starts. This is the only entry point to the worker loop."""
        import os
        import time
        import sys
        import fabric.network

        worker_parameters = 'parameters ppid={} pid={} {}'.format(os.getppid(), os.getpid(), self.description)
        self.log(worker_parameters)
        time.sleep(1)

        try:
            self.delay_execution()

            self.cloud.os_all()  # warm up to current cloud status
            self.set_status(status=self.STATUS_LOOPING)

            while not self.is_ready_to_finish():
                if self.pause_at_start > 0:
                    self.log('status=pause_loop{}_at_start time={} sec ...'.format(self.loop_counter + 1, self.pause_at_start))
                    time.sleep(1 if self.test_case.is_debug else self.pause_at_start)

                self.log('status=looping{} until={} other={}'.format(self.loop_counter + 1, self.run, self.status_dict))

                if not self.test_case.is_debug:
                    self.loop_worker()

                if self.pause_at_end > 0:
                    self.log('status=pause_loop{}_at_end time={} sec ...'.format(self.loop_counter + 1, self.pause_at_end))
                    time.sleep(1 if self.test_case.is_debug else self.pause_at_end)

                self.log('status=finish_loop{} until={} {} ...'.format(self.loop_counter + 1, self.run, self.status_dict))
                self.loop_counter += 1

        except RuntimeError as ex:
            self.log_exception()
        except Exception as ex:
            frame = sys.exc_traceback
            while frame.tb_next:
                frame = frame.tb_next
            self.errors.append(str(self) + ': ' + str(ex).replace('\\', '') + ' ' + frame.tb_frame.f_code.co_filename + ':' + str(frame.tb_lineno))
            self.log_exception()
            fabric.network.disconnect_all()
        finally:
            time.sleep(1)  # sleep to align log output
            self.set_status(status=self.STATUS_FINISHED)
            self.log('status=finish after loop={} until={} {}'.format(self.loop_counter, self.run, self.status_dict))
            self.log(80*'-')
            return self

    def failed(self, message, is_stop_running):
        self.log(self.STATUS_FAILED + str(message))
        self.failures.append('{}: {}'.format(self, message))
        if is_stop_running:
            raise RuntimeError(str(message))

    def passed(self, message):
        self.log(self.STATUS_PASSED + message)
        self.successes.append('{}: {}'.format(self, message))
