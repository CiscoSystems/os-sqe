from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class TestCaseResult(WithLogMixIn):
    PASSED = 'passed'
    FAILED = 'failed'
    SKIPED = 'skipped'
    ERRORED = 'errored'

    def __init__(self, tc):
        self.name = 'TCR ' + tc.path.split('-')[0] + ' '
        self.text = ''
        self.status = ''
        self.tims_url = ''

    def __repr__(self):
        return self.name + self.status.upper() + ' ' + self.tims_url


class TestCase(WithConfig, WithLogMixIn):

    def __init__(self, path, is_noclean, is_debug, cloud):
        import yaml
        import time

        self.path = path
        self.is_noclean = is_noclean
        self.is_debug = is_debug
        self.body_text = self.read_config_from_file(config_path=path, directory='ha', is_as_string=True)

        test_dic = yaml.load(self.body_text)
        must_be = {'Title', 'Folder', 'Description', 'UniqueID', 'PossibleDrivers', 'Workers'}
        assert type(test_dic) is dict, '{}: should be dictionary, no - please'.format(path)
        actual = set(test_dic.keys())
        assert actual == must_be, 'actual="{}", must be "{}"'.format(actual, must_be)

        self.title = test_dic['Title']
        self.folder = test_dic['Folder']
        self.description = test_dic['Description']
        self.unique_id = test_dic['UniqueID']
        self.possible_drivers = test_dic['PossibleDrivers']
        self.cloud = cloud
        self.time = time.time()  # time when the object was constructed

        self.workers = self.create_test_workers(test_dic.pop('Workers'))  # should be after self.cloud is assigned

    def __repr__(self):
        return 'TC=' + self.path.split('-')[0]

    @property
    def is_success(self):
        return all(map(lambda x: len(x.failures) == 0 and len(x.errors) == 0, self.workers))

    def create_test_workers(self, workers_lst):
        import importlib

        assert type(workers_lst) is list and len(workers_lst) >= 1

        worker_names_already_seen = []
        workers = []
        for worker_dic in workers_lst:  # list of dicts
            klass = worker_dic['class']
            path_to_module, class_name = klass.rsplit('.', 1)
            try:
                mod = importlib.import_module(path_to_module)
            except ImportError:
                raise ValueError('{}: tries to import {}.py which does not exist'.format(self.path, path_to_module))
            try:
                klass = getattr(mod, class_name)
            except AttributeError:
                raise ValueError('Please create class {} in {}.py'.format(class_name, path_to_module))
            worker = klass(test_case=self, args_dict=worker_dic)
            if worker.name in worker_names_already_seen:
                raise ValueError('{} uses name which is not unique in this test'.format(worker))
            else:
                worker_names_already_seen.append(worker.name)
            workers.append(worker)

        for worker in workers:
            for attr_name in [worker.ARG_MANDATORY_RUN, worker.ARG_MANDATORY_DELAY]:
                value = getattr(worker, attr_name)
                if type(value) is int:
                    continue
                wrong_names = set(value) - set(worker_names_already_seen)
                assert len(wrong_names) == 0, '{}.{} has invalid names: "{}". Valid: {}'.format(worker, attr_name, wrong_names, worker_names_already_seen)
        return workers

    def after_run(self, status_tbl, err_tbl):
        import time

        execution_time = time.time() - self.time
        tcr = TestCaseResult(tc=self)
        tcr.status = tcr.PASSED
        for w in self.workers:
            successes_txt = '\n'.join(w.successes)
            failures_txt = '\n'.join(w.failures)
            errors_txt = '\n'.join(w.errors)
            tcr.text += successes_txt + '\n' + failures_txt + '\n' + errors_txt
            if errors_txt + failures_txt:
                tcr.status = tcr.FAILED

        status_tbl.add_row([str(self), tcr.status, int(execution_time)])
        if tcr.text:
            err_tbl.add_row([str(self), tcr.text])
