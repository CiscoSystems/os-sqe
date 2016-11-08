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
        device_name = prompt(text='{lab} has: {nodes}\n(use "quit" to quit)\n node? '.format(lab=l, nodes=['lab', 'cloud'] + nodes))
        if device_name == 'cloud':
            d = DeployerExisting({'cloud': config_path.strip('.yaml'), 'hardware-lab-config': config_path}, version=None)
            device = d.execute({'servers': [], 'clouds': []})
        elif device_name == 'lab':
            device = l
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
            input_method_name = prompt(text='>>{0}<< operation?: '.format(device))
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
            lab_logger.info('executing {}'.format(input_method_name))
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
                device.log('RESULTS of {}():\n\n {}\n'.format(input_method_name, results))
            except Exception as ex:
                lab_logger.exception('\n Exception: {0}'.format(ex))


@task
def ha(lab_cfg_path, test_regex, is_debug=False, is_parallel=True, is_tims=True):
    """fab ha:g10,tc-vts\t\tRun all VTS tests on lab 'g10'
        :param lab_cfg_path: which lab
        :param test_regex: regex to match some tc in $REPO/configs/ha
        :param is_debug: if True, do not run actual workers just test the infrastructure
        :param is_parallel: if False, switch off parallel execution and run in sequence
        :param is_tims: if True then publish results to TIMS
    """
    from lab.with_config import WithConfig
    from lab.logger import lab_logger

    lab_name = lab_cfg_path.rsplit('/', 1)[-1].replace('.yaml', '')

    available_tc = WithConfig.ls_configs(directory='ha')
    tests = sorted(filter(lambda x: test_regex in x, available_tc))

    if not tests:
        lab_logger.info('STATUS: STATUS_FAILED')
        raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

    run_config_yaml = '{lab}-ha-{regex}.yaml'.format(lab=lab_name, regex=test_regex)
    with WithConfig.open_artifact(run_config_yaml, 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing.DeployerExisting: {cloud: %s, hardware-lab-config: %s}}\n' % (lab_name, lab_cfg_path))
        for i, test in enumerate(tests, start=1):
            f.write('runner{}:  {{lab.runners.runner_ha.RunnerHA: {{cloud: {}, task-yaml: "{}", is-debug: {}, is-parallel: {}, is-report-to-tims: {}}}}}\n'.format(10*i + 1,  lab_name, test, is_debug, is_parallel, is_tims))

    run_results = run(config_path='artifacts/' + run_config_yaml, version=None)

    lab_logger.info('Results: {}'.format(run_results))


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
    from lab.with_config import WithConfig

    lab_confirmed = filter(lambda x: lab in x, WithConfig.ls_configs())

    if not lab_confirmed:
        raise ValueError('There is no hardware configuration for lab {0}'.format(lab))

    n_tenants = int(max_vlans) / 2
    with open('configs/rally/{0}.yaml'.format(task_yaml)) as f:
        task_body = f.read()
        task_body = task_body.replace('{n_times}', max_vlans)
        task_body = task_body.replace('{concurrency}', concurrency)
        task_body = task_body.replace('{n_tenants}', '{0}'.format(n_tenants))

    with WithConfig.open_artifact('task-rally.yaml', 'w') as f:
        f.write(task_body)

    with WithConfig.open_artifact('rally-runner.yaml', 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing_osp7.DeployerExistingOSP7: {cloud: %s, hardware-lab-config: %s}}\n' % (lab, lab))
        f.write('runner:    {{lab.runners.runner_rally.RunnerRally: {{cloud: {lab}, hardware-lab-config: {lab}, task-yaml: artifacts/task-rally.yaml, rally-repo: "{repo}", rally-patch: "{patch}" }}}}\n'.format(
            lab=lab, repo=rally_repo, patch=rally_patch))
    run('artifacts/rally-runner.yaml')


@task
@decorators.print_time
def run(config_path, version):
    """fab run:bxb-run-rally\t\tGeneral: run any job specified by yaml.
        :param config_path: path to valid run specification, usually one of yaml from $REPO/configs/run
        :param version: specify a version of the product
    """
    from lab.base_lab import BaseLab

    l = BaseLab(yaml_name=config_path, version=version)
    return l.run()


@task
def conf():
    """fab conf\t\t\t\tTries to create lab configuration yaml
    """
    from lab.configurator import LabConfigurator

    c = LabConfigurator()
    c.execute()


@task
@decorators.print_time
def ansible():
    from collections import namedtuple
    from ansible.parsing.dataloader import DataLoader
    from ansible.vars import VariableManager
    from ansible.inventory import Inventory
    from ansible.playbook.play import Play
    from ansible.executor.task_queue_manager import TaskQueueManager
    from ansible.plugins.callback import CallbackBase
    from lab.logger import lab_logger

    class ResultCallback(CallbackBase):
        def __init__(self):
            super(ResultCallback, self).__init__()

        def v2_runner_on_ok(self, result, **kwargs):
            lab_logger.info(result)

    variable_manager = VariableManager()
    loader = DataLoader()
    options = namedtuple('Options', ['connection', 'module_path', 'forks', 'become', 'become_method', 'become_user', 'check'])(connection='local',
                                                                                                                               module_path=None,
                                                                                                                               forks=100,
                                                                                                                               become=None,
                                                                                                                               become_method=None,
                                                                                                                               become_user=None,
                                                                                                                               check=False)
    passwords = dict(vault_pass='secret')

    # create inventory and pass to var manager
    inventory = Inventory(loader=loader, variable_manager=variable_manager, host_list=['10.23.221.142'])
    variable_manager.set_inventory(inventory)

    # create play with tasks
    play_source = dict(name="Ansible Play", hosts='10.23.221.142', gather_facts='no', tasks=[
                            dict(action=dict(module='shell', args='ls'), register='shell_out'),
                            dict(action=dict(module='debug', args=dict(msg='{{shell_out.stdout}}')))
                            ]
                       )

    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    tqm = None
    try:
        tqm = TaskQueueManager(inventory=inventory, variable_manager=variable_manager, loader=loader, options=options, passwords=passwords, stdout_callback=ResultCallback())
        res = tqm.run(play)
        lab_logger.info('Ansible Result: {}'.format(res))
    finally:
        if tqm is not None:
            tqm.cleanup()


@task
@decorators.print_time
def collect_info(lab_config_path, regex):
    from lab.laboratory import Laboratory
    from lab.deployers.deployer_existing import DeployerExisting

    l = Laboratory(lab_config_path)
    d = DeployerExisting({'cloud': lab_config_path.strip('.yaml'), 'hardware-lab-config': lab_config_path}, version=None)
    try:
        c = d.execute({'servers': [], 'clouds': []})
        c.r_collect_information(regex=regex, comment='')
    except RuntimeError:
        pass  # it's ok if cloud is not yet deployed in the lab
    l.r_collect_information(regex=regex, comment='')
