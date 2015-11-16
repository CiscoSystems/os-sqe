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


def repeat_until_not_false(n_repetitions, time_between_repetitions):
    """Repeat decorated function until function returns True or not empty object"""
    import functools
    import time

    def decorator(function):
        @functools.wraps(function)
        def decorated_func(*args, **kwargs):
            for i in xrange(n_repetitions):
                result = function(*args, **kwargs)
                if result:
                    return result
                else:
                    time.sleep(time_between_repetitions)

        return decorated_func
    return decorator
