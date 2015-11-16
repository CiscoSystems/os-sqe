import os
from fabric.api import env, prefix
from contextlib import contextmanager
import logging
import functools
import time
import re
import sys

from fabs import LAB, WORKSPACE, DEFAULT_SETTINGS, _get_virtenv, _get_tempest_virtenv


env.update(DEFAULT_SETTINGS)

logger = logging.getLogger('ROBOT')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('robot.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)
logger.addHandler(fh)


def timed(func):
    @functools.wraps(func)
    def newfunc(*args, **kwargs):
        startTime = time.time()
        func(*args, **kwargs)
        elapsedTime = time.time() - startTime
        logger.info('TIMED: Function [{}] finished in {} sec'.format(
            func.__name__, int(elapsedTime)))

    return newfunc


@contextmanager
def virtualenv(path):
    activate = os.path.normpath(os.path.join(path, "bin", "activate"))
    if not os.path.exists(activate):
        raise OSError("Cannot activate virtualenv %s" % path)
    with prefix('. %s' % activate):
        yield


def virtual(func, envpath=None):
    @functools.wraps(func)
    def newfunc(*args, **kwargs):
        if envpath == "tempest":
            venv = _get_tempest_virtenv()
        else:
            venv = _get_virtenv()
        with virtualenv(venv):
            logger.info("Executing in virtualenv: {venv}".format(venv=venv))
            func(*args, **kwargs)

    return newfunc


def intempest(func):
    return virtual(func, envpath="tempest")


def get_lab_vm_ip():
    path = os.path.join(WORKSPACE, "openstack-sqe",
                        "tools", "cloud", "cloud-templates", "lab.yaml")
    try:
        with open(path) as f:
            labs = f.read()
    except Exception as e:
        logger.error("Exception when loading lab.yaml\n%s" % str(e))
        sys.exit(1)
    net, ip = re.search(LAB + r":\s*net_start: ([\.\d]+)\s*ip_start: (\d+)",
                        labs, re.MULTILINE).groups(1)
    return os.getenv('HOST_IP', net + "." + ip)
