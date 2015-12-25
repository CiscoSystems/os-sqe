from lab.runners import Runner


def starter(item_description):
    import time
    from lab import logger
    from lab.laboratory import Laboratory

    log = logger.create_logger(item_description.pop('log-name'))

    delay = item_description.get('delay', 0)
    if delay:
        log.info('Delaying start by {0} secs...'.format(delay))
        item_description.pop('delay')
    time.sleep(delay)

    func = item_description.pop('function')
    lab = Laboratory(config_path=item_description.pop('lab_name'))
    lab.cloud = item_description.pop('cloud')

    log.info('Start {0}'.format(item_description))
    func(lab, log, item_description)


class RunnerHA(Runner):
    def sample_config(self):
        return {'cloud': 'cloud name', 'hardware-lab-config': 'g10.yaml', 'task-yaml': 'task-ha.yaml'}

    def __init__(self, config):
        super(RunnerHA, self).__init__(config=config)
        self.cloud_name = config['cloud']
        self.task_yaml_path = config['task-yaml']
        self.task_body = self.read_config_from_file(config_path=self.task_yaml_path, directory='ha')
        self.lab_name = config['hardware-lab-config']

    def execute(self, clouds, servers):
        import importlib
        import multiprocessing

        items_to_run = []
        for arguments in self.task_body:
            module_path = arguments.pop('method')
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, 'start')
                arguments.update({'function': func, 'log-name': module_path, 'lab_name': self.lab_name, 'cloud': clouds[0]})
                items_to_run.append(arguments)
            except ImportError:
                raise Exception('{0} failed to import'.format(module_path))

        pool = multiprocessing.Pool(len(items_to_run))
        pool.map(starter, items_to_run)
