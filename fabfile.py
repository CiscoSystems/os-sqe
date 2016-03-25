#!/usr/bin/env python
from fabric.api import task
from lab import decorators


@task
def cmd(config_path):
    """fab cmd:g10\t\t\t\t\tRun single command on lab device.
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


@task
@decorators.print_time
def deploy(config_path, topology='VLAN'):
    """fab deploy:g10\t\t\t\tDeploy the lab from scratch.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
        :param topology: VLAN or VXLAN
     """
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=config_path)
    l.configure_for_osp7(topology=topology)


@task
def g10():
    """fab g10\t\t\t\t\t\tShortcut for fab deploy_lab:g10"""
    deploy(config_path='configs/g10.yaml')


@task
def g8():
    """fab g8\t\t\t\t\t\tShortcut for fab deploy_lab:g8"""
    deploy(config_path='configs/g8.yaml')


@task
def ha(lab, test_name, do_not_clean=False):
    """fab ha:g10,tc812,no_clean\tRun HA. "tcall" means all tests.
        :param lab: name from $REPO/configs/*.yaml
        :param test_name: test name to run - some yaml from configs/ha folder
        :param do_not_clean: if True then the lab will not be cleaned before running test
    """
    from lab.with_config import actual_path_to_config, ls_configs

    if not lab.endswith('.yaml'):
        lab += '.yaml'
    available_labs = ls_configs()
    if lab not in available_labs:
        raise ValueError('{lab} is not defined. Available labs: {labs}'.format(lab=lab, labs=available_labs))

    if test_name == 'tcall':
        tests = sorted(filter(lambda x: x.startswith('tc'), ls_configs(directory='ha')))
    else:
        tests = [actual_path_to_config(yaml_path=test_name, directory='ha').split('\\')[-1]]

    run_config_yaml = '{lab}-ha-{tc}.yaml'.format(lab=lab.split('.')[0], tc=test_name)
    with open(run_config_yaml, 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing_osp7.DeployerExistingOSP7: {cloud: %s, hardware-lab-config: %s}}\n' % (lab, lab))
        for i, test in enumerate(tests, start=1):
            if not do_not_clean:
                f.write('runner%s:  {lab.runners.runner_ha.RunnerHA: {cloud: %s, hardware-lab-config: %s, task-yaml: clean.yaml}}\n' % (10*i, lab, lab))
            f.write('runner%s:  {lab.runners.runner_ha.RunnerHA: {cloud: %s, hardware-lab-config: %s, task-yaml: "%s"}}\n' % (10*i + 1,  lab, lab, test))

    run(config_path=run_config_yaml)


@task
@decorators.print_time
def osp7(config_path):
    """fab osp7:g10\t\t\t\tMake conf file for OSP7. No work with hardware.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=config_path)
    l.create_config_file_for_osp7_install()


@task
@decorators.print_time
def rally(lab, concurrency, max_vlans, task_yaml, rally_repo='https://git.openstack.org/openstack/rally.git', rally_patch=''):
    """fab rally:g10,2,0,200\t\tRun rally with 2 threads for 0-200 vlans.
    :param lab: lab name - one of yaml in $REPO/configs
    :param concurrency: how many parallel threads
    :param max_vlans: right margin of vlan range
    :param task_yaml: specify task yaml, one from $REPO/configs/rally
    :param rally_repo: specify rally git repo if needed
    :param rally_patch: specify review if needed
    """
    from lab.with_config import ls_configs, open_artifact

    lab_confirmed = filter(lambda x: lab in x, ls_configs())

    if not lab_confirmed:
        raise ValueError('There is no hardware configuration for lab {0}'.format(lab))

    n_tenants = int(max_vlans) / 2
    with open('configs/rally/{0}.yaml'.format(task_yaml)) as f:
        task_body = f.read()
        task_body = task_body.replace('{n_times}', max_vlans)
        task_body = task_body.replace('{concurrency}', concurrency)
        task_body = task_body.replace('{n_tenants}', '{0}'.format(n_tenants))

    with open_artifact('task-rally.yaml', 'w') as f:
        f.write(task_body)

    with open_artifact('rally-runner.yaml', 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing_osp7.DeployerExistingOSP7: {cloud: %s, hardware-lab-config: %s}}\n' % (lab, lab))
        f.write('runner:    {{lab.runners.runner_rally.RunnerRally: {{cloud: {lab}, hardware-lab-config: {lab}, task-yaml: artifacts/task-rally.yaml, rally-repo: "{repo}", rally-patch: "{patch}" }}}}\n'.format(
            lab=lab, repo=rally_repo, patch=rally_patch))
    run('artifacts/rally-runner.yaml')


@task
@decorators.print_time
def run(config_path):
    """fab run:bxb-run-rally\t\tGeneral: run any job specified by yaml.
        :param config_path: path to valid run specification, usually one of yaml from $REPO/configs/run
    """
    from lab.base_lab import BaseLab

    l = BaseLab(yaml_name=config_path)
    l.run()
