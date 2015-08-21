def print_time(function):
    """Print time spent by decorated function"""
    import functools
    import time
    from lab.logger import lab_logger

    @functools.wraps(function)
    def decorated_func(*args, **kwargs):
        start_time = time.time()
        result = function(*args, **kwargs)
        lab_logger.info('TIMED: Function [{0}] finished in {1} sec'.format(function.__name__, int(time.time() - start_time)))
        return result

    return decorated_func
