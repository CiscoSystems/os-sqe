import logging


class JsonFormatter(logging.Formatter):
    def __init__(self):
        import os

        self._jenkins_tag = os.getenv('BUILD_TAG', 'no_jenkins')
        self._deployer_tag = 'not implemented'

        super(JsonFormatter, self).__init__()

    def format(self, record):
        import re
        import json

        def split_pairs():
            for key_value in re.split(pattern=';', string=record.message):  # 'a=b  ; c=d=43 ; k=5' will produce {'a':'b', 'c': 'd=43', 'k':5}
                if '=' in key_value:
                    key, value = key_value.split('=', 1)
                    key = key.strip()
                    if not key:
                        continue
                    try:
                        value = int(value)
                    except ValueError:
                        value = value.strip()
                        if '@timestamp' not in key:
                            value = value.replace('-', '')
                            value = value.replace(':', '')
                    d[key] = value

        d = {}
        if record.exc_text:
            d['EXCEPTION'] = record.exc_text.replace('\n', '')
        split_pairs()
        if '@timestamp' not in d:
            d['@timestamp'] = self.formatTime(record=record, datefmt="%Y-%m-%dT%H:%M:%S.000Z")
        d['name'] = record.name
        d['deployer-info'] = self._deployer_tag
        d['jenkins'] = self._jenkins_tag
        return json.dumps(d)


class JsonFilter(logging.Filter):
    def filter(self, record):
        return record.exc_text or '=' in record.message


class Logger(object):
    def __init__(self, name=None):
        import os

        self._logger = None
        ans = os.getenv('DISABLE_SQE_LOG', 'NO-NO')  # disable log is needed for correct processing ansible inventory in $repo/inventory.py
        if ans == 'NO-NO':
            self._create_logger(name)

    def _create_logger(self, name):
        import inspect
        import os
        from lab.with_config import WithConfig

        stack = inspect.stack()
        logger = logging.getLogger(name or stack[1][3])
        logger.setLevel(level=logging.DEBUG)

        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(logging.Formatter(fmt='[%(asctime)s %(levelname)s] %(name)s: %(message)s'))
        logger.addHandler(console)

        if 'vmtp' in os.listdir('/var/log'):
            logstash = logging.FileHandler('/var/log/vmtp/sqe.log')
            logstash.setLevel(logging.INFO)
            logstash.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s [%(name)s] %(message)s'))
            logger.addHandler(logstash)

        sqe_log_name, json_log_name = WithConfig.get_log_file_names()

        artifacts_sqe = logging.FileHandler(sqe_log_name)
        artifacts_sqe.setLevel(logging.INFO)
        artifacts_sqe.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s [%(name)s] %(message)s'))
        logger.addHandler(artifacts_sqe)

        artifacts_json = logging.FileHandler(json_log_name)
        artifacts_json.setLevel(logging.INFO)
        artifacts_json.setFormatter(JsonFormatter())
        artifacts_json.addFilter(JsonFilter())
        logger.addHandler(artifacts_json)

        logging.captureWarnings(True)
        self._logger = logger

    def debug(self, *args):
        if self._logger:
            self._logger.debug(*args)

    def info(self, *args):
        if self._logger:
            self._logger.info(*args)

    def warning(self, *args):
        if self._logger:
            self._logger.warning(*args)

    def exception(self, *args):
        if self._logger:
            self._logger.exception(*args)

    def error(self, *args):
        if self._logger:
            self._logger.error(*args)

    def _for_section(self, message, is_start):
        if self._logger:
            self._logger.info('{} {} {}'.format('START ' if is_start else 'FINISH', message, (200 - len(message)) * '-'))

    def section_start(self, message):
        self._for_section(message=message, is_start=True)

    def section_end(self, message):
        self._for_section(message=message, is_start=False)


lab_logger = Logger('LAB-LOG')
