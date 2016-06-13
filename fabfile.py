#!/usr/bin/env python
from fabric.api import task
from lab import decorators


@task
def cmd(config_path):
    """fab cmd:g10\t\t\t\tRun single command on lab device.
        :param config_path: path to valid hardware lab configuration, usually one of yaml in $REPO/configs
    """
    from fabric.operations import prompt
    from six import print_
    from lab.laboratory import Laboratory
    from lab.deployers.deployer_existing import DeployerExisting
    from lab.logger import lab_logger

    l = Laboratory(config_path=config_path)
    nodes = sorted(map(lambda node: node.get_id(), l.get_nodes_by_class()))
    while True:
        device_name = prompt(text='{lab} has: "cloud" and:\n {nodes}\n(use "quit" to quit)\n node? '.format(lab=l, nodes=nodes))
        if device_name == 'cloud':
            d = DeployerExisting({'cloud': config_path, 'hardware-lab-config': config_path})
            device = d.wait_for_cloud([])
        elif device_name in ['quit', 'q', 'exit']:
            return
        elif device_name not in nodes:
            print_(device_name, 'is not available')
            continue
        else:
            device = l.get_node_by_id(device_name)
        method_names = [x for x in dir(device) if not x.startswith('_')]
        print_(device, ' has: \n', '\n'.join(method_names), '\n(use "node" to get back to node selection)')
        while True:
            input_method_name = prompt(text='\n\n>>{0}<< operation?: '.format(device))
            if input_method_name in ['quit', 'q', 'exit']:
                return
            elif input_method_name == 'node':
                break
            elif input_method_name in ['r', 'rpt']:
                print_(device, ' has: \n', '\n'.join(method_names), '\n(use "node" to get back to node selection)')
                continue
            else:
                methods_in_filter = filter(lambda mth: input_method_name in mth, method_names)
                if len(methods_in_filter) == 0:
                    lab_logger.info('{} is not available'.format(input_method_name))
                    continue
                elif len(methods_in_filter) == 1:
                    input_method_name = methods_in_filter[0]
                elif len(methods_in_filter) > 1:
                    lab_logger.info('input  "{}" matches:\n{}'.format(input_method_name, '\n'.join(methods_in_filter)))
                    continue
            method_to_execute = getattr(device, input_method_name)
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
            # noinspection PyBroadException
            try:
                results = method_to_execute(*arguments)
                lab_logger.info('\n>>{}<< RESULTS:\n\n{}\n'.format(device, results))
            except Exception as ex:
                lab_logger.exception('\n Exception: {0}'.format(ex))


@task
def ha(lab, test_regex, do_not_clean=False, is_tims=False):
    """fab ha:g10,tc-vts,no_clean\t\tRun all VTS tests on lab g10
        :param lab: which lab to use
        :param test_regex: regex to match some tc in $REPO/configs/ha
        :param do_not_clean: if True then the lab will not be cleaned before running test
        :param is_tims: if True then publish results to TIMS
    """
    import os
    from fabric.api import local
    from lab import with_config

    lab_path = with_config.actual_path_to_config(path=lab)
    lab_name = lab_path.rsplit('/', 1)[-1].replace('.yaml', '')

    available_tc = with_config.ls_configs(directory='ha')
    tests = sorted(filter(lambda x: test_regex in x, available_tc))

    run_config_yaml = '{lab}-ha-{regex}.yaml'.format(lab=lab_name, regex=test_regex)
    with with_config.open_artifact(run_config_yaml, 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing.DeployerExisting: {cloud: %s, hardware-lab-config: %s}}\n' % (lab_name, lab))
        for i, test in enumerate(tests, start=1):
            if not do_not_clean:
                f.write('runner%s:  {lab.runners.runner_ha.RunnerHA: {cloud: %s, hardware-lab-config: %s, task-yaml: clean.yaml}}\n' % (10*i, lab_name, lab_name))
            f.write('runner%s:  {lab.runners.runner_ha.RunnerHA: {cloud: %s, hardware-lab-config: %s, task-yaml: "%s"}}\n' % (10*i + 1,  lab_name, lab_name, test))

    run(config_path=run_config_yaml)

    results = {x: {'status': False, 'n_exceptions': 2} for x in tests}
    if 'pyats' in os.getenv('PATH'):
        pyast_template = with_config.read_config_from_file('pyats.template', 'pyats', is_as_string=True)
        pyats_body = pyast_template.format(results)
        with with_config.open_artifact('pyats_job.py', 'w') as f:
            f.write(pyats_body)
        # noinspection PyBroadException
        try:
            local('easypy artifacts/pyats_job.py -no_archive ' + ('-tims_post -tims_dns "tims/Tcbr2p"' if is_tims else ''))
        except:
            pass


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
