import logging


class JsonFormatter(logging.Formatter):
    def __init__(self):
        import os

        self._repo_tag = os.system('git describe --always')
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
        d['sqe-repo-tag'] = self._repo_tag
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
        ans = os.getenv('DISABLE_SQE_LOG', 'NO-NO')
        if ans == 'NO-NO':
            self._create_logger(name)

    def _create_logger(self, name):
        import inspect
        import os
        from lab.with_config import WithConfig

        os.system('rm *.log')
        text_log_name, json_log_name = WithConfig.get_log_file_names()
        formatter = logging.Formatter(fmt='[%(asctime)s %(levelname)s] %(name)s:  %(message)s')

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(text_log_name)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        json_handler = logging.FileHandler(json_log_name)
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JsonFormatter())
        json_handler.addFilter(JsonFilter())

        stack = inspect.stack()
        logger = logging.getLogger(name or stack[1][3])
        logger.setLevel(level=logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.addHandler(json_handler)

        logging.captureWarnings(True)
        self._logger = logger

    def info(self, *args):
        if self._logger:
            self._logger.info(*args)

    def warning(self, *args):
        if self._logger:
            self._logger.warning(*args)

    def exception(self, *args):
        if self._logger:
            self._logger.exception(*args)


lab_logger = Logger('LAB-LOG')
