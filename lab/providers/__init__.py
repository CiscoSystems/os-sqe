import abc
from lab.WithConfig import WithConfig
from lab.WithRunMixin import WithRunMixin


class Provider(WithConfig, WithRunMixin):
    @abc.abstractmethod
    def wait_for_servers(self):
        """Make sure that all servers in provider are indeed online"""
        pass


def read_config_from_file(yaml_path):
    import os
    import yaml
    if not os.path.isfile(yaml_path):
        raise IOError('{0} not found. Provide full path to your yaml config file'.format(yaml_path))
    with open(yaml_path) as f:
        return yaml.load(f)
