import logging

formatter = logging.Formatter(fmt='[%(asctime)s %(levelname)s] %(name)s:  %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler('iron-lady.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)


class JsonFormatter(logging.Formatter):
    def __init__(self):
        super(JsonFormatter, self).__init__()

    def format(self, record):
        import re
        import json

        d = {}
        for key_value in re.split(pattern='[ ,]', string=record.message):
            if '=' in key_value:
                key, value = key_value.split('=')
                value = value.strip()
                key = key.strip()
                if not key:
                    continue
                try:
                    value = int(value)
                except ValueError:
                    pass
                d[key] = value
        d['timestamp'] = self.formatTime(record=record, datefmt="%Y-%m-%d %H:%M:%S")
        d['name'] = record.name
        return json.dumps(d)


json_handler = logging.FileHandler('json.log')
json_handler.setLevel(logging.DEBUG)
json_handler.setFormatter(JsonFormatter())


def create_logger(name=None):
    import inspect

    stack = inspect.stack()
    logger = logging.getLogger(name or stack[1][3])
    logger.setLevel(level=logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(json_handler)
    return logger


lab_logger = create_logger(name='LAB-LOG')
