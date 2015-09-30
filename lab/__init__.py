import abc
import os


CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'configs'))


class Server(object):
    def __init__(self, ip, username, password, hostname='Unknown',
                 ssh_public_key='N/A', ssh_port=22,
                 ipmi_ip=None, ipmi_username=None, ipmi_password=None,
                 pxe_mac=None, ip_mac=None):
        self.ip = ip
        self.ip_mac = ip_mac
        self.hostname = hostname
        self.username = username
        self.password = password
        self.ssh_public_key = ssh_public_key
        self.ssh_port = ssh_port

        self.ipmi_ip = ipmi_ip
        self.ipmi_username = ipmi_username
        self.ipmi_password = ipmi_password
        self.pxe_mac = pxe_mac

    def __repr__(self):
        return 'sshpass -p {0} ssh {1}@{2}'.format(self.password, self.username, self.ip)


class LabConfigException(Exception):
    def __init__(self,  lab_class, sample_config, config, message=''):
        self.__class_name = lab_class
        self.__sample_config = sample_config
        self.__config = config
        self.__message = message
        self.__form_exception()

    @property
    def message(self):
        return self.__message

    @message.setter
    def message(self, message):
        self.__message = message
        self.__form_exception()

    def __form_exception(self):
        super(LabConfigException, self).__init__('in {klass}:\n{msg}\nSample config: {sample}\nProvided config: {provided}'.format(msg=self.__message,
                                                                                                                                   klass=self.__class_name,
                                                                                                                                   sample=self.__sample_config,
                                                                                                                                   provided=self.__config))


class WithStatusMixIn(object):
    def __repr__(self):
        attributes = vars(self)
        return '\n'.join(['{0}:\t{1}'.format(key, attributes[key]) for key in sorted(attributes.keys()) if not key.startswith('_')])

    def status(self):
        from logger import lab_logger
        lab_logger.info('status of {0}:\n{1}'.format(type(self), self))


class WithConfig(object):
    CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'configs'))
    PRIVATE_KEY = os.path.join(CONFIG_DIR, 'keys', 'private')

    def __init__(self, config):
        self._exception = LabConfigException(lab_class=type(self), config=config, sample_config=self.sample_config())
        self.verify_config(sample_config=self.sample_config(), config=config)

    @abc.abstractmethod
    def sample_config(self):
        raise NotImplementedError('class {0} do not implement method sample_config()'.format(type(self)))

    def verify_config(self, sample_config, config, current_key=None):
        """Verify that config corresponds to sample_config"""
        import validators

        if isinstance(sample_config, list):
            if not len(config):
                self._exception.message = 'empty list'
                raise self._exception
            for element in config:
                self.verify_config(sample_config=sample_config[0], config=element, current_key=current_key)
        elif isinstance(sample_config, dict):
            for sample_key, sample_value in sample_config.iteritems():
                if sample_key not in config:
                    self._exception.message = 'Key "{0}" not in config'.format(sample_key)
                    raise self._exception
                if config[sample_key] is None:
                    self._exception.message = 'Value of "{0}" is empty'.format(sample_key)
                    raise self._exception
                self.verify_config(sample_config=sample_value, config=config[sample_key], current_key=sample_key)
        else:
            # from this point config and sample_config start to be simple values
            if type(sample_config) is basestring:
                if sample_config.startswith('http') and validators.url(config) is not True:
                    self._exception.message = 'Key "{0}" do not contain valid url: {1}'.format(current_key, config)
                    raise self._exception
                elif sample_config.startswith('email') and not validators.email(config):
                    self._exception.message = 'Key "{0}" do not contain valid email: {1}'.format(current_key, config)
                    raise self._exception
                elif sample_config.startswith('ipv4') and not validators.ipv4(config):
                    self._exception.message = 'Key "{0}" do not contain valid IPv4: {1}'.format(current_key, config)
                    raise self._exception
                elif sample_config.startswith('int'):
                    try:
                        int(config)
                    except ValueError:
                        self._exception.message = 'Key "{0}" do not contain valid int number: {1}'.format(current_key, config)
                        raise self._exception
            elif type(sample_config) is bool and type(config) is not bool:
                self._exception.message = 'Key "{0}" must be bool: {1}'.format(current_key, config)
                raise self._exception

    @staticmethod
    def wget_file(url, checksum, loc_dir=None):
        from fabric.api import settings, local, run

        loc = url.split('/')[-1]
        if loc_dir:
            run('mkdir -p {0}'.format(loc_dir))
            loc = os.path.abspath(os.path.join(loc_dir, loc))

        cmd_wget = 'test -e  {loc} || wget -nv {url} -O {loc}'.format(loc=loc, url=url)
        cmd_sha = 'sha256sum {loc}'.format(loc=loc)
        cmd_rm = 'rm {0}'.format(loc)
        with settings(warn_only=False):
            _ = local(cmd_wget) if loc_dir else run(cmd_wget)
            calc_checksum = local(cmd_sha, capture=True) if loc_dir else run(cmd_sha)
            if calc_checksum.split()[0] != checksum:
                _ = local(cmd_rm) if loc_dir else run(cmd_rm)
                raise RuntimeError('I deleted image {0} since it is broken (checksum is not matched). Re-run the script'.format(loc))
        return loc
