#!/usr/bin/env python
from fabric.api import task

from lab import decorators


@task
@decorators.print_time
def deploy_lab(config_path):
    """fab deploy_lab:g10 \t\t\t\t Deploy the given lab from scratch including FI&N9K configuration.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=config_path)
    l.configure_for_osp7()


@task
@decorators.print_time
def osp7_config(config_path):
    """fab osp7_config:g10 \t\t\t\t Create configuration file for osp7_bootstrap. Nothing will be done with N9K and alike.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=config_path)
    l.create_config_file_for_osp7_install()


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
def cmd(config_path):
    """fab cmd:g10 \t\t\t Run single command on G10 devices.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from fabric.operations import prompt
    from time import sleep
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=config_path)
    print l, ' has: ', sorted(l.get_nodes().keys())
    device_name = prompt(text='On which device you want to execute the command?')
    device = l.get_node(device_name)
    method_names = [x for x in dir(device) if not x.startswith('_')]
    print device,  ' has: \n', '\n'.join(method_names)
    method_name = prompt(text='Which operation you wanna execute?')
    if method_name == 'cmd':
        command = prompt(text='cmd requires command, please enter something like sh cdp nei:')
        results = device.cmd(command)
    else:
        method_to_execute = getattr(device, method_name)
        results = method_to_execute()

    sleep(1)
    print 'RESULTS:\n', results
