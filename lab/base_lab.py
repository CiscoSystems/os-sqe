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

        config = read_config_from_file(yaml_path=yaml_name, directory='run')
        for section_name, class_path_vs_config in sorted(config.iteritems()):
            class_path = class_path_vs_config.keys()[0]
            class_config = class_path_vs_config[class_path]
            a = class_path.split('.')
            module_path = '.'.join(a[:-1])
            class_name = a[-1]
            try:
                module = importlib.import_module(module_path)
                class_instance = getattr(module, class_name)(class_config)
            except (ValueError, ImportError):
                section_name_no_digits = section_name.strip('0123456789')
                section_dir = 'lab/' + section_name_no_digits + 's'
                classes = map(lambda name: section_dir.replace('/', '.') + '.' + name.replace('.py', ''), filter(lambda name: name.startswith(section_name_no_digits) and name.endswith('.py'), os.listdir(section_dir)))
                raise ValueError('in yaml {y} line {l}: Module "{mp}" is not defined! Use one of {c}'.format(y=yaml_name, l=class_path_vs_config, mp=module_path, c=classes))
            except AttributeError:
                raise ValueError('in yaml {y}: class {k} is not in {p}'.format(y=yaml_name, k=class_name, p=module_path))
            if type(class_instance).__name__.startswith('Provider'):
                self.providers.append(class_instance)
            elif type(class_instance).__name__.startswith('Deployer'):
                self.deployers.append(class_instance)
            elif type(class_instance).__name__.startswith('Runner'):
                self.runners.append(class_instance)

    def run(self):
        import time

        self.status()
        with open('summary.log', 'w') as f:
            for provider in self.providers:
                start_time = time.time()
                self.servers.extend(provider.wait_for_servers())
                f.write('Provider {0} runs in {0} seconds\n'.format(provider, time.time() - start_time))
            for deployer in self.deployers:
                start_time = time.time()
                self.clouds.append(deployer.wait_for_cloud(self.servers))
                f.write('Deployer {0} runs in {0} seconds\n'.format(deployer, time.time() - start_time))
            for runner in self.runners:
                start_time = time.time()
                runner.execute(self.clouds, self.servers)
                f.write('Runner {0} runs in {0} seconds\n'.format(runner, time.time() - start_time))
