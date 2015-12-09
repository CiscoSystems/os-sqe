from lab.runners import Runner


def starter(item_description):
    import time
    from lab import logger

    log = logger.create_logger(item_description.pop('log-name'))

    context = RunnerContext(item_description.pop('lab-cfg'))
    delay = item_description.get('delay', 0)
    log.info('Delaying start on {0} secs...'.format(delay))
    time.sleep(delay)
    log.info('Start')
    func = item_description.pop('function')
    func(context, log, item_description)


class RunnerContext(object):
    def __init__(self, lab_cfg):
        self.lab_cfg = lab_cfg

    def lab_id(self):
        return self.lab_cfg['lab-id']

    def ucsm_ip(self):
        return self.lab_cfg['ucsm']['host']

    def ucsm_username(self):
        return self.lab_cfg['ucsm']['username']

    def ucsm_password(self):
        return self.lab_cfg['ucsm']['password']

    def n9k_creds(self):
        return self.lab_cfg['n9k']


class RunnerHA(Runner):
    def sample_config(self):
        return {'cloud': 'cloud name', 'hardware-lab-config': 'path to valid hardware lab configuration', 'task-yaml': 'path to the valid task yaml file'}

    def __init__(self, config):
        from lab.WithConfig import read_config_from_file

        super(RunnerHA, self).__init__(config=config)
        self.cloud_name = config['cloud']
        self.task_yaml_path = config['task-yaml']
        self.task_body = read_config_from_file(yaml_path=self.task_yaml_path)
        self.lab_cfg = read_config_from_file(yaml_path=config['hardware-lab-config'])

    def execute(self, clouds, servers):
        import importlib
        import multiprocessing

        items_to_run = []
        for import_path, arguments in self.task_body.iteritems():
            try:
                module_path, func_name = import_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                func = getattr(module, func_name)
                arguments.update({'function': func, 'log-name': import_path, 'lab-cfg': self.lab_cfg})
                items_to_run.append(arguments)
            except ImportError:
                raise Exception('{0} failed to import'.format(import_path))

        pool = multiprocessing.Pool(len(items_to_run))
        pool.map(starter, items_to_run)
