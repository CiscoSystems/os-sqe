def section(message):
    """Log message before and after decorated function"""
    import functools
    import time
    from lab.with_log import lab_logger

    def decorator(fun):
        @functools.wraps(fun)
        def decorated_func(*args, **kwargs):
            time.sleep(2)
            lab_logger.section_start(fun.func_name)
            time.sleep(2)  # sleep to allow printing comes first
            start_time = time.time()
            result = fun(*args, **kwargs)
            time.sleep(2)
            lab_logger.section_end(fun.func_name + ' (actually it took {} secs)'.format(int(time.time() - start_time)))
            time.sleep(2)
            return result
        return decorated_func
    return decorator


def repeat_until_not_false(n_repetitions, time_between_repetitions):
    """Repeat decorated function until function returns True or not empty object"""
    import functools
    import time

    def decorator(fun):
        @functools.wraps(fun)
        def decorated_func(*args, **kwargs):
            for i in range(n_repetitions):
                result = fun(*args, **kwargs)
                if result:
                    return result
                else:
                    time.sleep(time_between_repetitions)

        return decorated_func
    return decorator
