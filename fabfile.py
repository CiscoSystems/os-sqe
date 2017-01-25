from fabric.api import task
import sys

if '.' not in sys.path:
    sys.path.append('.')


KNOWN_LABS = ['g7-2.yaml', 'marahaika.yaml', 'c42top.yaml', 'i13tb3.yaml']


@task
def cmd():
    """fab cmd\t\t\t\tRun single command on lab device
    """
    from fabric.operations import prompt
    import time
    from lab.laboratory import Laboratory
    from lab.deployers.deployer_existing import DeployerExisting
    from lab.with_log import lab_logger

    lab_cfg_path = get_user_input(owner='lab yaml', options_lst=KNOWN_LABS)
    l = Laboratory(config_path=lab_cfg_path)
    nodes = sorted(map(lambda node: node.get_node_id(), l.get_nodes_by_class()))
    while True:
        device_name = get_user_input(owner=l, options_lst=['lab', 'cloud'] + nodes)
        if device_name == 'cloud':
            d = DeployerExisting({'hardware-lab-config': lab_cfg_path})
            device = d.execute([])
        elif device_name == 'lab':
            device = l
        else:
            device = l.get_node_by_id(device_name)
        method_names = [x for x in dir(device) if not x.startswith('_')]
        while True:
            input_method_name = get_user_input(owner=device, options_lst=method_names + ['levup'])
            if input_method_name == 'levup':
                break

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
                time.sleep(1)  # sleep to prevent fabric prompt clashing with
            except Exception as ex:
                lab_logger.exception('\n Exception: {0}'.format(ex))


@task
def ha(lab_cfg_path, test_regex, is_debug=False, is_parallel=True):
    """fab ha:g10,str\t\t\tRun all tests with 'str' in name on g10
        :param lab_cfg_path: which lab
        :param test_regex: regex to match some tc in $REPO/configs/ha
        :param is_debug: if True, do not run actual workers just test the infrastructure
        :param is_parallel: if False, switch off parallel execution and run in sequence
    """
    from lab.with_config import WithConfig
    from lab.deployers.deployer_existing import DeployerExisting
    from lab.runners.runner_ha import RunnerHA

    available_tc = WithConfig.ls_configs(directory='ha')
    tests = sorted(filter(lambda x: test_regex in x, available_tc))

    if not tests:
        raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

    deployer = DeployerExisting(config={'lab-cfg-yaml-path': lab_cfg_path})
    cloud = deployer.execute([])

    exceptions = []
    for tst in tests:
        runner = RunnerHA(config={'cloud': cloud, 'task-yaml': tst, 'is-debug': is_debug, 'is-parallel': is_parallel})
        run_result = runner.execute(cloud)
        if run_result['expections']:
            exceptions.append(run_result['exceptions'])

    if exceptions:
        raise RuntimeError('Possible reason: {}'.format(exceptions))


@task
def rally(lab, concurrency, max_vlans, task_yaml, rally_repo='https://git.openstack.org/openstack/rally.git', rally_patch=''):
    """fab rally:g10,2,0,200\t\tRun rally with 2 threads for 0-200 vlans
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
def run(config_path, version):
    """fab run:bxb-run-rally\t\tGeneral: run any job specified by yaml
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

    LabConfigurator()


@task
def ansible():
    from collections import namedtuple
    from ansible.parsing.dataloader import DataLoader
    from ansible.vars import VariableManager
    from ansible.inventory import Inventory
    from ansible.playbook.play import Play
    from ansible.executor.task_queue_manager import TaskQueueManager
    from ansible.plugins.callback import CallbackBase
    from lab.with_log import lab_logger

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
def info(lab_config_path, regex):
    """fab info:g10,regex\t\t\tExec grep regex
    """
    from lab.laboratory import Laboratory
    from lab.deployers.deployer_existing import DeployerExisting

    l = Laboratory(lab_config_path)
    d = DeployerExisting({'cloud': lab_config_path.strip('.yaml'), 'hardware-lab-config': lab_config_path})
    try:
        servers_and_clouds = {'servers': [], 'clouds': []}
        d.execute(servers_and_clouds=servers_and_clouds)
        servers_and_clouds['clouds'][0].r_collect_information(regex=regex, comment='')
    except RuntimeError:
        pass  # it's ok if cloud is not yet deployed in the lab
    l.r_collect_information(regex=regex, comment='')


def get_user_input(owner, options_lst):
    from fabric.operations import prompt
    import sys

    sub_list = options_lst
    while True:
        choice = prompt('choose one of {}, q to cancel\nfor {}>'.format(sorted(sub_list), owner))
        if choice == 'q':
            sys.exit(2)
        sub_list = filter(lambda x: choice in x, sub_list)
        if len(sub_list) == 1:
            return sub_list[0]  # unique match , return it
        elif len(sub_list) == 0:
            sub_list = options_lst
            continue  # wrong input ask again with full list of options
        else:
            continue  # ask again with restricted list of options


@task
def bash():
    """fab bash\t\t\t\tDefine bash aliases for lab"""
    from lab.laboratory import Laboratory
    from fabric.api import local

    lab_cfg_path = get_user_input(owner='lab', options_lst=['g7-2.yaml', 'marahaika.yaml', 'c42top.yaml', 'i13tb3.yaml'])
    l = Laboratory(lab_cfg_path)
    file_name = 'tmp.aliases'
    local('rm -f ' + file_name)
    for node in l.get_nodes_by_class():
        cmds = node.get_ssh_for_bash()
        if type(cmds) is tuple:
            local('echo \'alias {}="{}"\' >> {}'.format(node.get_node_id(), cmds[0], file_name))
            local('echo \'alias cimc_{}="{}"\' >> {}'.format(node.get_node_id(), cmds[1], file_name))
        else:
            local('echo \'alias {}="{}"\' >> {}'.format(node.get_node_id(), cmds, file_name))
    local('echo \'PS1="({}) $PS1 "\' >> {}'.format(l, file_name))
