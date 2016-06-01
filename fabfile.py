#!/usr/bin/env python
from fabric.api import task
from lab import decorators


@task
def cmd(config_path):
    """fab cmd:g10\t\t\t\tRun single command on lab device.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from fabric.operations import prompt
    from time import sleep
    from lab.laboratory import Laboratory
    from lab.deployers.deployer_existing import DeployerExisting

    l = Laboratory(config_path=config_path)
    nodes = sorted(map(lambda node: node.name(), l.get_nodes()))
    while True:
        print l, 'has: cloud and', nodes
        device_name = prompt(text='On which device you want to execute the command?')
        if device_name == 'cloud':
            d = DeployerExisting({'cloud': config_path, 'hardware-lab-config': config_path})
            device = d.wait_for_cloud([])
        elif device_name not in nodes:
            print device_name, 'is not available'
            continue
        else:
            device = l.get_node(device_name)
        method_names = [x for x in dir(device) if not x.startswith('_')]
        print device,  ' has: \n', '\n'.join(method_names)
        while True:
            method_name = prompt(text='Which operation you wanna execute? ("quit" to exit, "node" to select new node) ')
            if method_name == 'quit':
                return
            elif method_name == 'node':
                break
            elif method_name not in method_names:
                print method_name, 'is not available'
                continue
            method_to_execute = getattr(device, method_name)
            parameters = method_to_execute.func_code.co_varnames[1:method_to_execute.func_code.co_argcount]
            arguments = []
            for parameter in parameters:
                argument = prompt(text='{p}=? '.format(p=parameter))
                if argument.startswith('['):
                    argument = argument.strip('[]').split(',')
                elif argument in ['True', 'true', 'yes']:
                    argument = True
                elif argument in ['False', 'false', 'no']:
                    argument = False
                arguments.append(argument)
            results = method_to_execute(*arguments)

            sleep(1)
            print '\n{0} RESULTS:\n\n'.format(device), results


@task
@decorators.print_time
def deploy(config_path, is_for_mercury=False, topology='VLAN'):
    """fab deploy:g10\t\t\t\tDeploy the lab from scratch.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
        :param is_for_mercury: True if mercury installer will be used, False if RH OSP
        :param topology: VLAN or VXLAN
     """
    from lab.laboratory import Laboratory

    l = Laboratory(config_path=config_path)
    if is_for_mercury:
        l.configure_for_mercury(topology=topology)
    else:
        l.configure_for_osp7(topology=topology)


@task
def ha(lab, test_name, do_not_clean=False):
    """fab ha:g10,tc812,no_clean\tRun HA. "tcall" means all tests.
        :param lab: name from $REPO/configs/*.yaml
        :param test_name: test name to run - some yaml from configs/ha folder
        :param do_not_clean: if True then the lab will not be cleaned before running test
    """
    from lab.with_config import actual_path_to_config, ls_configs

    # if not lab.endswith('.yaml'):
    #     lab += '.yaml'
    # available_labs = ls_configs()
    # if lab not in available_labs:
    #     raise ValueError('{lab} is not defined. Available labs: {labs}'.format(lab=lab, labs=available_labs))
    lab = actual_path_to_config(path=lab)

    if test_name == 'tcall':
        tests = sorted(filter(lambda x: x.startswith('tc'), ls_configs(directory='ha')))
    else:
        tests = [actual_path_to_config(path=test_name, directory='ha').split('\\')[-1]]

    run_config_yaml = '{lab}-ha-{tc}.yaml'.format(lab=lab.split('.')[0], tc=test_name)
    with open(run_config_yaml, 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing.DeployerExisting: {cloud: %s, hardware-lab-config: %s}}\n' % (lab, lab))
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
