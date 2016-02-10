from fabric.api import task

@task
def log(string_to_log):
    """fab test.log:'some message like a\=b'\t\t Test logging facility. Check file json.log after executing."""
    from lab.logger import create_logger

    l = create_logger('test-log')
    l.info(string_to_log)
