from fabric.api import task
from lab import CONFIG_DIR, decorators, LabConfigException, WithStatusMixIn


class BaseLab(WithStatusMixIn):
    sample_config = 'Try to provide at least section {provider: {ProviderClassName: {}}'

    def __init__(self, yaml_name):
        import importlib
        import os
        import yaml

        self.providers = []
        self.deployers = []
        self.runners = []

        self.servers = []

        yaml_path = yaml_name if os.path.isfile(yaml_name) else os.path.join(CONFIG_DIR, 'labs', yaml_name)
        if not os.path.isfile(yaml_path):
            folder = os.path.abspath(os.path.join(CONFIG_DIR, 'labs'))
            raise IOError('{0} not found. Provide full path or choose one of:\n{1}'.format(yaml_name, '\n'.join(filter(lambda name: name.endswith('.yaml'), os.listdir(folder)))))

        with open(yaml_path) as f:
            config = yaml.load(f)
            if not config:
                raise LabConfigException(lab_class=type(self), sample_config=self.sample_config, config=config, message='empty config')
            for section_name, class_name_vs_config in sorted(config.iteritems()):
                section_class_name = class_name_vs_config.keys()[0]
                section_class_config = class_name_vs_config[section_class_name]
                section_name_no_digits = ''.join([i for i in section_name if not i.isdigit()])  # section_name may contain digits: provider1 -> providers
                section_package = section_name_no_digits + 's'
                try:
                    module = importlib.import_module('lab.{package}.{klass}'.format(package=section_package, klass=section_class_name))
                except ImportError:
                    section_dir = 'lab/' + section_package
                    classes = map(lambda name: name.split('.')[0], filter(lambda name: name.startswith(section_name_no_digits.capitalize()), os.listdir(section_dir)))
                    message = '{0} {1} is not defined! Use one of {2}'.format(section_name, section_class_name, classes)
                    sample_config = '{' + section_name + ': {' + classes[0] + ': { some configuration which will be checked on next run } }'
                    raise LabConfigException(lab_class=type(self), sample_config=sample_config, config=config, message=message)
                section_class_instance = getattr(module, section_class_name)(section_class_config)
                if section_name.startswith('provider'):
                    self.providers.append(section_class_instance)
                elif section_name.startswith('deployer'):
                    self.deployers.append(section_class_instance)
                elif section_name.startswith('runner'):
                    self.runners.append(section_class_instance)
                else:
                    raise LabConfigException(lab_class=type(self), sample_config='known sections: provider[1-9], deployer[1-9], runner[1-9]',
                                             config=config, message='do not know what to do with section {0}'.format(section_name))

    def run(self):
        self.status()
        for provider in self.providers:
            self.servers.extend(provider.wait_for_servers())
        for deployer in self.deployers:
            deployer.wait_for_cloud(self.servers)
        for runner in self.runners:
            runner.run(self.servers)


__all__ = ['run_lab']


@task
@decorators.print_time
def run_lab(yaml_name):
    """Run lab provided by yaml config"""

    l = BaseLab(yaml_name=yaml_name)
    l.run()
