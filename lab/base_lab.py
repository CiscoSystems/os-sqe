import abc
from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn
from lab.with_status import WithStatusMixIn


class LabWorker(WithConfig, WithLogMixIn):
    @abc.abstractmethod
    def execute(self, servers_and_clouds):
        raise NotImplemented

    def __repr__(self):
        return u'{}'.format(type(self).__name__)


class BaseLab(WithStatusMixIn):
    sample_config = 'Try to provide at least section {provider: {ProviderClassName: {}}'

    def __init__(self, yaml_name, version):
        import importlib
        import os
        from lab.with_config import read_config_from_file

        self.providers = []
        self.deployers = []
        self.runners = []

        self._servers_and_clouds = {'servers': [], 'clouds': []}
        self._results = []

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
            class_instance = klass(config=class_config, version=version)
            if type(class_instance).__name__.startswith('Provider'):
                self.providers.append(class_instance)
            elif type(class_instance).__name__.startswith('Deployer'):
                self.deployers.append(class_instance)
            elif type(class_instance).__name__.startswith('Runner'):
                self.runners.append(class_instance)

    def run(self):
        import time
        from lab.logger import lab_logger

        self.status()

        separator = 100 * '-'
        for obj in self.providers + self.deployers + self.runners:
            start_time = time.time()
            lab_logger.info(separator)
            lab_logger.info('Call {}.execute()...'.format(obj))
            lab_logger.info(separator)
            status = obj.execute(self._servers_and_clouds)
            self._results.append({'class': str(obj), 'spent_time': time.time() - start_time, 'status': status})
        return self._results
