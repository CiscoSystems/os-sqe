import logging


class JsonFormatter(logging.Formatter):
    def format(self, record):
        import json

        def split_pairs():
            for key_value in record.message.split():  # 'a=b   c=d=43  k=5 all bla ...' will produce {'a':'b', 'c': 'd=43', 'k':5}
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
        return json.dumps(d)


class MainLogFormatter(logging.Formatter):
    def format(self, record):
        return self._fmt.format(time='' if '+-' in record.msg else self.formatTime(record, datefmt=self.datefmt), msg=record.msg).strip()


class JsonFilter(logging.Filter):
    def filter(self, record):
        return record.exc_text or '=' in record.message


class CheckStringFilter(logging.Filter):
    def __init__(self, name):
        super(CheckStringFilter, self).__init__()
        self.check_name = name

    def filter(self, record):
        return self.check_name in record.message


class SlackHandler(logging.Handler):
    def handle(self, record):
        import requests
        import json

        msg = record.getMessage()
        if 'tims/warp' in msg:
            data = json.dumps({"channel": "#autoreports", "username": "leeroy", "text": '{}'.format(record.getMessage())})
            requests.post(url='https://hooks.slack.com/services/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', data=data)


class WithLogMixIn(object):

    @staticmethod
    def log_to_artifact(name, body):
        from lab.with_config import WithConfig

        with WithConfig.open_artifact(name, 'w') as f:
            f.write(body)

    def single_cmd_output(self, cmd, ans):
        n = 200
        return '\n' + n * 'v' + '\n' + str(self) + '> ' + cmd + '\n' + n * '^' + '\n' + ans + '\n' + n * '-' + '\n\n'

    @staticmethod
    def log_grep_cmd(log_files, regex, minutes=0):
        """regex: 'string: some regexp to be used in grep, empty means all',
        'minutes': 'int: 10 -> filter out all messages older then 10 minutes ago, 0 means no filter'}
        """

        cmd = "sudo grep -r '{}' {} ".format(regex, log_files)
        cmd += 'sed -n "/^$(date +%Y-%m-%d\ %H:%M --date="{min} min ago")/, /^$(date +%Y-%m-%d\ %H:%M)/p" '.format(min=minutes) if minutes else ''
        return cmd

    def log(self, message):
        lab_logger.info('{:35} {}'.format(self, message))

    def log_warning(self, message):
        lab_logger.warning(str(self) + ' ' + message)

    def log_error(self, message):
        lab_logger.error(str(self) + ' ' + message)

    def log_exception(self):
        lab_logger.exception(str(self) + ' EXCEPTION')

    def log_debug(self, message):
        lab_logger.debug(str(self) + ' ' + message)


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

        stack = inspect.stack()
        logger = logging.getLogger(name or stack[1][3])
        logger.setLevel(level=logging.DEBUG)

        console = logging.StreamHandler()
        debug_h = logging.FileHandler('a_debug.log', mode='w')
        json_h = logging.FileHandler('a_json.log', mode='w')
        cmd_vts_h = logging.FileHandler('a_cmd_vts.log', mode='w')
        cmd_os_h = logging.FileHandler('a_cmd_os.log', mode='w')
        nfvbench_h = logging.FileHandler('a_nfvbench.log', mode='w')
        slack_h = SlackHandler()
        results_h = logging.FileHandler('a_results.log', mode='w')

        console.setLevel(logging.INFO)
        debug_h.setLevel(logging.DEBUG)
        json_h.setLevel(logging.INFO)
        slack_h.setLevel(logging.INFO)
        results_h.setLevel(logging.INFO)

        console.setFormatter(MainLogFormatter(fmt='{time} {msg}', datefmt='%b%d %H:%M:%S'))
        debug_h.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s'))
        json_h.setFormatter(JsonFormatter())
        results_h.setFormatter(logging.Formatter(fmt='%(message)s'))

        json_h.addFilter(JsonFilter())
        cmd_os_h.addFilter(CheckStringFilter('openrc'))
        cmd_vts_h.addFilter(CheckStringFilter('8888'))
        nfvbench_h.addFilter(CheckStringFilter('nfvbench'))
        results_h.addFilter(CheckStringFilter('+--'))

        logger.addHandler(console)
        logger.addHandler(debug_h)
        logger.addHandler(json_h)
        logger.addHandler(cmd_vts_h)
        logger.addHandler(cmd_os_h)
        logger.addHandler(slack_h)
        logger.addHandler(nfvbench_h)
        logger.addHandler(results_h)

        if os.path.isdir('/var/log') and 'vmtp' in os.listdir('/var/log'):
            logstash = logging.FileHandler('/var/log/vmtp/sqe.log')
            logstash.setLevel(logging.INFO)
            logstash.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s [%(name)s] %(message)s'))  # the format is important for logstash processing
            logger.addHandler(logstash)

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
            self._logger.info('{} {} {}'.format(message, 'START ' if is_start else 'FINISH', (80 - len(message)) * '-'))

    def section_start(self, message):
        self._for_section(message=message, is_start=True)

    def section_end(self, message):
        self._for_section(message=message, is_start=False)


lab_logger = Logger(name='LAB-LOG')
