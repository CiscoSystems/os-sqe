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
            d = DeployerExisting({'cloud': config_path.strip('.yaml'), 'hardware-lab-config': config_path})
            device = d.wait_for_cloud([])
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
def ha(lab, test_regex, is_exact_match=False, is_debug=False, is_run_cleanup=False, is_tims=False):
    """fab ha:g10,tc-vts\t\tRun all VTS tests on lab 'g10'
        :param lab: which lab
        :param test_regex: regex to match some tc in $REPO/configs/ha
        :param is_exact_match: if true, interpret test_regex as exact match to choose single test
        :param is_debug: is True, switch off parallel execution and run in sequence
        :param is_run_cleanup: if True, run cleanup before anything else
        :param is_tims: if True then publish results to TIMS
    """
    import os
    from fabric.api import local
    from lab import with_config
    from lab.logger import lab_logger

    lab_name = lab.rsplit('/', 1)[-1].replace('.yaml', '')

    available_tc = with_config.ls_configs(directory='ha')
    tests = sorted(filter(lambda x: test_regex == x if is_exact_match else test_regex in x, available_tc))

    if not tests:
        raise ValueError('Provided regexp "{}" does not match any tests'.format(test_regex))

    run_config_yaml = '{lab}-ha-{regex}.yaml'.format(lab=lab_name, regex=test_regex)
    with with_config.open_artifact(run_config_yaml, 'w') as f:
        f.write('deployer:  {lab.deployers.deployer_existing.DeployerExisting: {cloud: %s, hardware-lab-config: %s}}\n' % (lab_name, lab))
        for i, test in enumerate(tests, start=1):
            if is_run_cleanup:
                f.write('runner%s:  {lab.runners.runner_ha.RunnerHA: {cloud: %s, hardware-lab-config: %s, task-yaml: clean.yaml}}\n' % (10*i, lab_name, lab_name))
            f.write('runner{}:  {{lab.runners.runner_ha.RunnerHA: {{cloud: {}, hardware-lab-config: {}, task-yaml: "{}", is-debug: {}}}}}\n'.format(10*i + 1,  lab_name, lab_name, test, is_debug))

    run_results = run(config_path='artifacts/' + run_config_yaml)

    lab_logger.info('Results: {}'.format(run_results))
    if 'pyats' in os.getenv('PATH'):
        pyast_template = with_config.read_config_from_file('pyats.template', 'pyats', is_as_string=True)
        pyats_body = pyast_template.format(run_results)
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
    return l.run()


@task
@decorators.print_time
def junit_to_tims(junitxml, outpyats_jobfile):
    import os
    import xml.etree.ElementTree as ET
    from lab import with_config

    tims_ids = []
    test_names = []
    test_cases = {}

    tree = ET.parse(junitxml)
    root = tree.getroot()
    assert root.tag == "testsuite"
    for testcase in root:
        assert testcase.tag == "testcase"

        newcase = {}
        name = testcase.attrib["name"]
        name_split = name.rsplit('_', 1)
        short_name, tims_id = '', ''
        if len(name_split) > 1:
            short_name, tims_id = name_split

        class_path, class_name = testcase.attrib["classname"].rsplit('.', 1)

        newcase['name'] = testcase.attrib["name"]
        newcase['short_name'] = short_name
        newcase['tims_id'] = tims_id
        newcase['testclass'] = testcase.attrib["classname"]
        newcase['duration'] = float(testcase.attrib["time"])

        for child in testcase:
            if child.tag == "skipped":
                newcase['skipped'] = child.text
                if "message" in child.attrib:
                    newcase['skipped_msg'] = child.attrib["message"]
            elif child.tag == "system-out":
                newcase['stdout'] = child.text
            elif child.tag == "system-err":
                newcase['stderr'] = child.text
            elif child.tag == "failure":
                newcase['failure'] = child.text
                if "message" in child.attrib:
                    newcase['failure_msg'] = child.attrib["message"]
            elif child.tag == "error":
                newcase['failure'] = child.text
                if "message" in child.attrib:
                    newcase['failure_msg'] = child.attrib["message"]

        tims_ids.append(tims_id)
        test_names.append(name)

        if class_name not in test_cases:
            test_cases[class_name] = []
        test_cases[class_name].append(newcase)


    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__)) + '/configs/pyats'))
    template = env.get_template('pyats.jinja2')

    with with_config.open_artifact(outpyats_jobfile, 'w') as f:
        f.write(template.render(results=test_cases))


@task
def conf():
    """fab conf\t\t\t\tTries to create lab configuration yaml
    """
    from fabric.operations import prompt
    import validators
    import six
    from lab.nodes.n9k import Nexus
    from lab.with_config import open_artifact

    n9k_ip = prompt(text='Enter one of your N9K OOB IP: ')
    n9k_username = 'admin'
    n9k_password = 'CTO1234!'
    if not validators.ipv4(n9k_ip):
        six.print_('{} is not valid IP, existing'.format(n9k_ip))
        return
    n9k_username = prompt(text='Enter username for N9K at {} (default is {}): '.format(n9k_ip, n9k_username)) or n9k_username
    n9k_password = prompt(text='Enter password for N9K at {} (default is {}): '.format(n9k_ip, n9k_password)) or n9k_password

    n9k = Nexus(node_id=1, role=Nexus.ROLE, lab='fake-lab')
    n9k.set_oob_creds(ip=n9k_ip, username=n9k_username, password=n9k_password)
    cdp = n9k.n9_show_cdp_neighbor()
    lldp = n9k.n9_show_lldp_neighbor()

    with open_artifact(name='new_lab.yaml', mode='w') as f:
        f.write('lab-id: ???? # integer in ranage (0,99). supposed to be unique in current L2 domain since used in MAC pools\n')
        f.write('lab-name: ???? # any string to be used on logging\n')
        f.write('lab-type: ???? # supported types: MERCURY, OSPD\n')
        f.write('description-url: "https://wiki.cisco.com/display/OPENSTACK/SJ19-121-????"\n')
        f.write('\n')
        f.write('dns: [171.70.168.183]\n')
        f.write('ntp: [171.68.38.66]\n')
        f.write('\n')
        f.write('nodes: [\n')
        f.write(']\n\n')
        f.write('peer-links: [ # Section which describes peer-links in the form {own-id: n92, own-port:  1/46, peer-id: n91, peer-port: 1/46, port-channel: pc100}\n')
        f.write(']\n')


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
def tims():
    from lab.tims import Tims

    t = Tims()
    t.publish_tests_to_tims()


@task
@decorators.print_time
def collect_info(lab_config_path):
    from lab.laboratory import Laboratory
    from lab.deployers.deployer_existing import DeployerExisting

    l = Laboratory(lab_config_path)
    d = DeployerExisting({'cloud': lab_config_path.strip('.yaml'), 'hardware-lab-config': lab_config_path})
    c = d.wait_for_cloud([])
    c.r_collect_information('')
    l.r_collect_information('')
