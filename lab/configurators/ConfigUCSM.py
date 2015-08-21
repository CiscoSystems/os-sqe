from lab.configurators import Configurator


class ConfiguratorUCSMError:
    pass


class ConfiguratorUCSM(Configurator):

    SampleConfiguration = {'host': 'ip or FQDN of UCSM', 'user': 'username on UCSM', 'password': 'password on UCSM', 'backup_name': 'name of backup or full path'}
    def __init__(self, config):
        try:
            self.ucsm_host = config['host']
            self.ucsm_user = config['user']
            self.ucsm_password = config['password']
            self.ucsm_backup_path = config['password']
        except KeyError:
            raise ConfiguratorUCSMError(self.wrong_config_message(''))

    def config(self):
        from fabs.ucsm import ucsm_backup

        ucsm_backup(host=self.ucsm_host, username=self.ucsm_user, password=self.ucsm_password, backup_path=self.ucsm_backup_path)
