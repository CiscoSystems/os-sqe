from lab.runners import Runner


# noinspection PyBroadException
def starter(item_description):
    import time
    from lab import logger

    log = logger.create_logger(item_description.pop('log-name'))

    delay = item_description.get('delay', 0)
    duration = item_description.get('duration', 3)
    period = item_description.get('period', 0)

    if delay:
        log.info('Delaying start by {0} secs...'.format(delay))
        item_description.pop('delay')
    time.sleep(delay)

    func = item_description.pop('function')
    cloud = item_description.pop('cloud')
    lab = cloud.mediator.lab()
    lab.cloud = cloud

    log.info('status=Start arguments={0}'.format(item_description))
    start_time = time.time()
    end_time = start_time + duration
    try:
        while time.time() < end_time:
            func(lab, log, item_description)
            time.sleep(period)
    except:
        log.exception('EXCEPTION')


class RunnerHA(Runner):
    def sample_config(self):
        return {'cloud': 'cloud name', 'hardware-lab-config': 'g10.yaml', 'task-yaml': 'task-ha.yaml'}

    def __init__(self, config):
        super(RunnerHA, self).__init__(config=config)
        self.cloud_name = config['cloud']
        self.task_yaml_path = config['task-yaml']
        self.task_body = self.read_config_from_file(config_path=self.task_yaml_path, directory='ha')
        if not self.task_body:
            raise Exception('Empty Test task list. Please check the file: {0}'.format(self.task_yaml_path))
        self.lab_name = config['hardware-lab-config']

    def __repr__(self):
        return u'{0}-{1}'.format(self.lab_name, self.task_yaml_path)

    def execute(self, clouds, servers):
        import importlib
        import multiprocessing
        import fabric.network
        from lab.logger import create_logger

        try:
            cloud = filter(lambda x: x.name == self.cloud_name, clouds)[0]
        except IndexError:
            raise RuntimeError('Cloud <{0}> is not provided by deployment phase'.format(self.cloud_name))

        log = create_logger(name=str(self))

        items_to_run = []
        for arguments in self.task_body:
            module_path = arguments.pop('method')
            try:
                module = importlib.import_module(module_path)
                func = getattr(module, 'start')
                arguments.update({'function': func, 'log-name': module_path, 'cloud': cloud})
                items_to_run.append(arguments)
            except ImportError:
                raise Exception('{0} failed to import'.format(module_path))

        fabric.network.disconnect_all()  # we do that since URL: http://stackoverflow.com/questions/29480850/paramiko-hangs-at-get-channel-while-using-multiprocessing

        pool = multiprocessing.Pool(len(items_to_run))

        log.info('status=Start')
        pool.map(starter, items_to_run)
        log.info('status=Finish')
