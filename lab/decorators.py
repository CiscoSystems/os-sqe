def section(message, estimated_time=None):
    """Log message before and after decorated function"""
    import functools
    import time
    from lab.with_log import lab_logger

    def decorator(function):
        @functools.wraps(function)
        def decorated_func(*args, **kwargs):
            time.sleep(2)
            lab_logger.section_start(message=message + (' usually it takes {} secs'.format(estimated_time) if estimated_time else ''))
            time.sleep(2)  # sleep to allow printing comes first
            start_time = time.time()
            result = function(*args, **kwargs)
            time.sleep(2)
            lab_logger.section_end(message=message + ' (actually it took {} secs)'.format(int(time.time() - start_time)))
            time.sleep(2)
            return result
        return decorated_func
    return decorator


def repeat_until_not_false(n_repetitions, time_between_repetitions):
    """Repeat decorated function until function returns True or not empty object"""
    import functools
    import time

    def decorator(function):
        @functools.wraps(function)
        def decorated_func(*args, **kwargs):
            for i in range(n_repetitions):
                result = function(*args, **kwargs)
                if result:
                    return result
                else:
                    time.sleep(time_between_repetitions)

        return decorated_func
    return decorator
