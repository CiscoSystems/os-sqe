#!/usr/bin/env python
import os
from fabric.api import task, local
from fabs.common import timed, virtual
from fabs.common import logger as log
from fabs import LVENV, CVENV, LAB
from lab import decorators
from fabs import tempest, snap, coverage
from fabs import jenkins_reports
from lab import BaseLab
from lab.providers import cobbler, ucsm, n9k
from lab.runners import rally
from lab.configurators import osp7_install
from tools import ucsm_tempest_conf
from tools import osp_net_cisco


@timed
def venv(private=False):
    log.info("Installing packages from requirements")
    # local("sudo apt-get install -y $(cat requirements_packages)")
    venv_path = CVENV
    if private:
        venv_path = LVENV
    if not os.path.exists(venv_path):
        log.info("Creating virtual environment in {dir}".format(dir=venv_path))
        local("virtualenv --setuptools %s" % venv_path)
    else:
        log.info("Virtual environment in {dir} already exists".format(dir=venv_path))


@timed
@virtual
def requirements():
    log.info("Installing python modules from requirements")
    local("pip install -Ur requirements")


@task
@virtual
def flake8():
    """ Make a PEP8 check for code """
    local("flake8 --max-line-length=120 --show-source --exclude=.env1 . || echo")


@task
@timed
def init(private=False):
    """ Prepare virtualenv and install all requirements """
    venv(private=private)
    requirements()


@task
@timed
@virtual
def destroy():
    """ Destroying all lab machines and networks """
    log.info("Destroying lab {lab}".format(lab=LAB))
    local("python ./tools/cloud/create.py -l {lab} -x".format(lab=LAB))


def deploy_lab(config_path):
    from lab.providers import ucsm
    from lab.providers import cobbler
    from lab.configurators import osp7_install

    cobbler.configure_for_osp7(yaml_path=config_path)
    ucsm.configure_for_osp7(yaml_path=config_path)
    osp7_install.configure_for_osp7(yaml_path=config_path)


@task
@decorators.print_time
def g10():
    """ (Re)deploy  G10 lab"""
    deploy_lab(config_path='configs/g10.yaml')


@task
@decorators.print_time
def g8():
    """ (Re)deploy  G8 lab"""
    deploy_lab(config_path='configs/g8.yaml')


@task
@decorators.print_time
def run(config_path):
    """ Run HA specific test cases
    :param config_path: specify what to run
    """
    from lab.BaseLab import BaseLab

    l = BaseLab(yaml_name=config_path)
    l.run()
