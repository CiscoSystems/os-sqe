from lab.with_status import WithStatusMixIn


class BaseLab(WithStatusMixIn):
    sample_config = 'Try to provide at least section {provider: {ProviderClassName: {}}'

    def __init__(self, yaml_name):
        import importlib
        import os
        from lab.with_config import read_config_from_file

        self.providers = []
        self.deployers = []
        self.runners = []

        self.servers = []
        self.clouds = []

        config = read_config_from_file(config_path=yaml_name, directory='run')
        for section_name, class_path_vs_config in sorted(config.items()):
            module_class_path, class_config = class_path_vs_config.items()[0]
            module_path, class_name = module_class_path.rsplit('.', 1)
            try:
                module = importlib.import_module(module_path)
                klass = getattr(module, class_name)
            except ImportError:
                section_name_no_digits = section_name.strip('0123456789')
                section_dir = 'lab/' + section_name_no_digits + 's'
                classes = map(lambda name: section_dir.replace('/', '.') + '.' + name.replace('.py', ''), filter(lambda name: name.startswith(section_name_no_digits) and name.endswith('.py'), os.listdir(section_dir)))
                raise ValueError('yaml {y} section {l}: Module "{mp}" is not defined! Use one of:\n {c}'.format(y=yaml_name, l=section_name, mp=module_path, c=classes))
            except AttributeError:
                raise ValueError('in yaml {y}: class {k} is not in {p}'.format(y=yaml_name, k=class_name, p=module_path))
            class_instance = klass(class_config)
            if type(class_instance).__name__.startswith('Provider'):
                self.providers.append(class_instance)
            elif type(class_instance).__name__.startswith('Deployer'):
                self.deployers.append(class_instance)
            elif type(class_instance).__name__.startswith('Runner'):
                self.runners.append(class_instance)

    def run(self):
        import time
        from lab.logger import lab_logger

        results = {}
        self.status()
        for provider in self.providers:
            start_time = time.time()
            lab_logger.info('Running {}'.format(provider))
            self.servers.extend(provider.wait_for_servers())
            results[str(provider)] = 'spent_time={0}'.format(time.time() - start_time)
        for deployer in self.deployers:
            lab_logger.info('Running {}'.format(deployer))
            start_time = time.time()
            cloud = deployer.wait_for_cloud(self.servers)
            self.clouds.append(cloud)
            results[str(deployer)] = {'spent_time': time.time() - start_time, 'status': True}
        for runner in self.runners:
            lab_logger.info('Running {}'.format(runner))
            start_time = time.time()
            res = runner.execute(self.clouds, self.servers)
            res['spent_time'] = time.time() - start_time
            results[str(runner)] = res
        return results
