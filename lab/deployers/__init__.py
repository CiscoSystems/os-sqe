import abc
from lab.with_config import WithConfig


class Deployer(WithConfig):
    @abc.abstractmethod
    def wait_for_cloud(self, list_of_servers):
        """Make sure that cloud is up and running on the provided list of servers
        :param list_of_servers: list of server provided during provisioning phase
        """
        pass

    def __repr__(self):
        return u'{}'.format(type(self).__name__)

    def log(self, message, level='info'):
        from lab.logger import lab_logger

        message = '{}: {}'.format(self, message)
        if level == 'info':
            lab_logger.info(message)
        elif level == 'warning':
            lab_logger.warning(message)
        elif level == 'exception':
            lab_logger.exception(message)
        else:
            raise RuntimeError('Specified "{}" logger level is not known'.format(level))
