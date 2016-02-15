#!/usr/bin/env python
from fabric.api import task

from lab import decorators, fi


@task
@decorators.print_time
def deploy_lab(config_path):
    """fab deploy_lab:g10 \t\t\t\t Deploy the given lab from scratch including FI&N9K configuration.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from lab.providers import fi
    from lab.providers import cobbler
    from lab.configurators import osp7_install

    cobbler.configure_for_osp7(yaml_path=config_path)
    fi.configure_for_osp7(yaml_path=config_path)
    osp7_install.configure_for_osp7(yaml_path=config_path)


@task
@decorators.print_time
def osp7_config(config_path):
    """fab osp7_config:g10 \t\t\t\t Create configuration for osp7_bootstrap.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from lab.configurators import osp7_install

    osp7_install.configure_for_osp7(yaml_path=config_path)


@task
def g10():
    """fab g10 \t\t\t\t\t Shortcut for fab deploy_lab:g10"""
    deploy_lab(config_path='configs/g10.yaml')


@task
def g8():
    """fab g8 \t\t\t\t\t Shortcut for fab deploy_lab:g8"""
    deploy_lab(config_path='configs/g8.yaml')


@task
@decorators.print_time
def run(config_path):
    """fab run:bxb-run-rally \t\t\t Run any job specified by yaml.
        :param config_path: path to valid run specification, usually one of yaml from $REPO/configs/run
    """
    from lab.base_lab import BaseLab

    l = BaseLab(yaml_name=config_path)
    l.run()


@task
def hag10(test_name, do_not_clean=False):
    """fab hag10:tc812,no_clean \t\t\t Run G10 HA. fab hag10:all will run all tests.
        :param test_name: test name to run - some yaml from configs/ha folder
        :param do_not_clean: if True then the lab will not be cleaned before running test
    """
    from lab.with_config import actual_path_to_config, ls_configs

    if test_name == 'all':
        tests = sorted(filter(lambda x: x.startswith('tc'), ls_configs(directory='ha')))
    else:
        tests = [actual_path_to_config(yaml_path=test_name, directory='ha')]

    run_config_yaml = 'g10-ha-{0}.yaml'.format(test_name)
    with open(run_config_yaml, 'w') as f:
        f.write('deployer:  {DeployerExistingOSP7: {cloud: g10, hardware-lab-config: g10.yaml}}\n')
        for i, test in enumerate(tests, start=1):
            if not do_not_clean:
                f.write('runner%s:  {RunnerHA: {cloud: g10, hardware-lab-config: g10.yaml, task-yaml: clean.yaml}}\n' % (10*i))
            f.write('runner%s:  {RunnerHA: {cloud: g10, hardware-lab-config: g10.yaml, task-yaml: %s}}\n' % (10*i + 1,  test))

    run(config_path=run_config_yaml)


@task
def ucsmg10(cmd):
    """fab ucsmg10:'scope org; sh service-profile' \t Run single command on G10 UCSM.
        :param cmd: command to be executed
    """
    from lab.laboratory import Laboratory
    from lab.fi import FI

    l = Laboratory(config_path='g10.yaml')
    ucsm_ip, ucsm_username, ucsm_password = l.ucsm_creds()
    ucsm = FI(ucsm_ip, ucsm_username, ucsm_password)
    ucsm.cmd(cmd)


@task
def n9kg10(cmd):
    """fab n9kg10:'sh cdp nei' \t\t\t Run single command on G10 N9K.
        :param cmd: command to be executed
    """
    from lab.laboratory import Laboratory
    from lab.n9k import Nexus
    l = Laboratory(config_path='g10.yaml')
    n9k_ip, _, n9k_username, n9k_password = l.n9k_creds()
    nx = Nexus(n9k_ip, n9k_username, n9k_password)
    print nx.cmd(cmd)
