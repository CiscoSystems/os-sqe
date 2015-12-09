import logging


formatter = logging.Formatter(fmt='[%(asctime)s %(levelname)s] %(name)s:  %(message)s')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler('iron-lady.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)


def create_logger(name=None):
    import inspect

    stack = inspect.stack()
    logger = logging.getLogger(name or stack[1][3])
    logger.setLevel(level=logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

lab_logger = create_logger(name='LAB-LOG')
