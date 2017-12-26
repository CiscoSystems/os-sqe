import sys
from fabric.api import task

if '.' not in sys.path:
    sys.path.append('.')


from tools.fabric_test import test


@task
def cmd():
    """fab cmd\t\t\t\tRun single command on lab device
    """
    import inspect
    from fabric.operations import prompt
    import time
    from lab.deployers.deployer_existing_light import DeployerExistingLight
    from lab.with_log import lab_logger
    from lab.laboratory import Laboratory

    pod_names = Laboratory.MERCURY_DIC['pods'].keys()
    l_and_s_names = map(lambda x: 'l' + x, pod_names) + map(lambda x: 's' + x, pod_names)
    _, pod_name = get_user_input(obj=l_and_s_names)
    root = Laboratory.create(lab_name=pod_name[1:], is_interactive=True) if pod_name[0] == 'l' else DeployerExistingLight(pod_name[1:])()
    obj = root
    while True:
        obj, method = get_user_input(obj=obj)
        try:
            obj.log('{} executing ......................'.format(method))
            time.sleep(1)
            parameters = method.func_code.co_varnames[1:method.func_code.co_argcount]
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
            results = method(*arguments) if arguments else method()
            time.sleep(1)
            obj.log('{}() returns:\n\n {}\n'.format(method, results))
        except Exception as ex:
            lab_logger.exception('\n Exception: {0}'.format(ex))
        prompt('')


@task
def ha(pod, regex, noclean=False, debug=False):
    """fab ha:g10,str\t\t\tRun all tests with 'str' in name on g10
        :param pod: IP to ssh to management node
        :param regex: regex to match some tc in $REPO/configs/ha
        :param debug: if True debug parallel infrastructure
        :param noclean: if True, do not cleanup objects created during test, leave them from post analysis
    """
    from lab.runners.runner_ha import RunnerHA

    yes = ['true', 'True', 'yes', 'Yes', 'y', 'Y']
    RunnerHA().run(pod_name=pod, test_regex=regex, is_noclean=str(noclean) in yes, is_debug=str(debug) in yes)


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
def run(config_path):
    """fab run:bxb-run-rally\t\tGeneral: run any job specified by yaml
        :param config_path: path to valid run specification, usually one of yaml from $REPO/configs/run
    """
    from lab.base_lab import BaseLab

    some = BaseLab(yaml_name=config_path)
    return some.run()


@task
def info(pod_name=None, regex=None):
    """fab info:g10,regex\t\t\tExec grep regex
    """
    from lab.laboratory import Laboratory

    pod = Laboratory.create(lab_name=pod_name)
    pod.r_collect_info(regex=regex, comment=regex)


def get_user_input(obj, parent=None):
    from fabric.operations import prompt
    import sys
    import inspect
    from prettytable import PrettyTable

    if type(obj) is list:
        if len(obj) == 0:
            print 'The list is empty, back to {}'.format(parent)
            return get_user_input(obj=parent)
        fields_dic = {str(x): x for x in obj}
        all_names = sorted(fields_dic.keys())
        methods_dic = {}
    elif type(obj) in [str, unicode, basestring]:
        return obj, obj
    else:
        methods = [x for x in inspect.getmembers(obj, predicate=lambda x: inspect.isfunction(x) or inspect.ismethod(x)) if not x[0].startswith('__')]
        fields = [x for x in inspect.getmembers(obj, predicate=lambda x: not inspect.isfunction(x) and not inspect.ismethod(x)) if not x[0].startswith('__')]

        tbl = PrettyTable(['', str(obj), str(obj.__class__)])
        map(lambda x: tbl.add_row(['method', x[0], '']), methods)
        tbl.add_row(['', '', ''])
        map(lambda x: tbl.add_row(['field', x[0], str(x[1])]), fields)
        print tbl
        methods_dic = {x[0]: x[1] for x in methods}
        fields_dic = {x[0]: x[1] for x in fields}
        all_names = [x[0] for x in methods + fields]

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield ' * '.join(lst[i:i + n])

    sub_names = all_names
    while True:
        sub_list_str = '\n'.join(chunks(lst=sub_names, n=14))
        print '\n'
        choice = prompt(text='{} * a * q: '.format(sub_list_str))
        if choice == 'q':
            sys.exit(2)
        if choice == 'a':
            sub_names = all_names
            continue
        sub_list = filter(lambda x: choice in x, sub_names)
        if len(sub_list) == 1:
            choice = sub_list[0]
        if choice in sub_list:
            print 'Using:', choice, '\n'
            if choice in methods_dic:
                return obj, methods_dic[choice]
            if choice in fields_dic:
                return get_user_input(obj=fields_dic[choice], parent=obj)
        elif len(sub_list) == 0:
            continue  # wrong input ask again with the same list of names
        else:
            sub_names = sub_list
            continue  # ask again with restricted list of names


@task
def bash():
    """fab bash\t\t\t\tDefine bash aliases for lab"""
    from lab.laboratory import Laboratory
    from lab.nodes.lab_server import LabServer
    from lab.nodes.virtual_server import VirtualServer

    pod = Laboratory.create(lab_name=get_user_input(obj=Laboratory.MERCURY_DIC.keys()))
    aliases = []
    for node in pod.nodes.values():
        if not isinstance(node, VirtualServer):
            aliases.append('alias z{n}="sshpass -p {p} ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip}"'.format(n=node.id, p=node.oob_password, u=node.oob_username, ip=node.oob_ip))  # cimc
        if isinstance(node, LabServer):
            ip, username, password = (node.proxy.ssh_ip + ' ' + 'ssh -o StrictHostKeyChecking=no ' + node.id, node.proxy.ssh_username, node.proxy.ssh_password) if node.proxy else (node.ssh_ip, node.ssh_username, node.ssh_password)
            password = ' sshpass -p ' + password + ' ' if password else ''  # if password is None use the key pair to ssh
            aliases.append('alias {n}="{p}ssh -t -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no {u}@{ip}"'.format(p=password, n=node.id, u=username, ip=ip))  # ssh

    with open('tmp.aliases', 'w') as f:
        f.write('\n'.join(sorted(aliases)))
        f.write('\nPS1="({}) $PS1 "\n'.format(pod))
