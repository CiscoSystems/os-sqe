#!/usr/bin/env python
from StringIO import StringIO
import argparse
import os
import yaml
from fabric.api import sudo, settings, run, hide, put, cd, get, local, parallel, \
    execute, env
from fabric.contrib.files import append, exists
from utils import collect_logs, warn_if_fail, quit_if_fail, update_time, \
    collect_logs_devstack

DESCRIPTION = 'Installer for Devstack.'
CISCO_TEMPEST_REPO = 'https://github.com/CiscoSystems/tempest.git'
DEVSTACK_REPO = 'https://github.com/openstack-dev/devstack.git'
DEVSTACK_DEFAULT = './tools/deployers/devstack-configs/devstack_single_node.yaml'
DEVSTACK_BRANCH = 'master'
DEV_CONF_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             "devstack-configs")
TEMPEST_CONF = """enable_service tempest
TEMPEST_REPO={repo}
TEMPEST_BRANCH={branch}"""


@parallel
def install(aggregated_configs, apt_cacher_proxy=None,
            patch="", proxy="", devstack_repo="", devstack_br="", quiet=False):
    verbose = []
    fab_settings = aggregated_configs[env.host]["fab_settings"]
    local_conf = aggregated_configs[env.host]["devstack_config"]
    config_files = aggregated_configs[env.host]["config_files"]
    hostname = aggregated_configs[env.host]["hostname"]
    exec_command_before = aggregated_configs[env.host]["exec_commands_before"]
    exec_command_after = aggregated_configs[env.host]["exec_commands_after"]
    if quiet:
        verbose = ['output', 'running', 'warnings']
    with settings(**fab_settings), hide(*verbose):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100",
                   use_sudo=True)
        if proxy:
            warn_if_fail(put(StringIO(
                'Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy", use_sudo=True))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining",
                             use_sudo=True))
        if apt_cacher_proxy:
            warn_if_fail(
                put(StringIO('Acquire::http { Proxy "{url}"; };'.format(
                    url=apt_cacher_proxy)),
                    "/etc/apt/apt.conf.d/02proxy", use_sudo=True))
        update_time(sudo)
        warn_if_fail(sudo("apt-get update"))
        warn_if_fail(sudo("apt-get install -y git python-pip"))
        warn_if_fail(
            run("git config --global user.email 'test.node@example.com';"
                "git config --global user.name 'Test Node'"))
        if exists("devstack"):
            with cd("devstack"):
                warn_if_fail(run("./unstack.sh"))
        run("rm -rf ~/devstack")
        quit_if_fail(run(
            "git clone -b {branch} {devstack}".format(devstack=devstack_repo,
                                                      branch=devstack_br)))
        if patch:
            with cd("devstack"):
                warn_if_fail(
                    run(
                        "git fetch https://review.openstack.org/openstack-dev/devstack {patch} "
                        "&& git cherry-pick FETCH_HEAD".format(patch=patch)))
        warn_if_fail(put(StringIO(local_conf), "devstack/local.conf"))
        if exec_command_before:
            run(exec_command_before)
        if config_files:
            for path, conf_file in config_files.iteritems():
                warn_if_fail(put(StringIO(conf_file), path))
        with cd("devstack"):
            warn_if_fail(run("./stack.sh"))
        path = os.environ.get("WORKSPACE", os.getcwd())
        if os.path.exists(
                "{path}/id_rsa_{key}".format(path=path, key=hostname)):
            path = os.environ.get("WORKSPACE", os.getcwd())
            put("{path}/id_rsa_{key}".format(path=path, key=hostname),
                "~/.ssh/id_rsa")
            put("{path}/id_rsa_{key}.pub".format(path=path, key=hostname),
                "~/.ssh/id_rsa.pub")
            put("{0}/id_rsa_all.pub".format(path), "/tmp/all_authorized")
            warn_if_fail(run("chmod 500 ~/.ssh/id_rsa"))
            warn_if_fail(
                run("cat /tmp/all_authorized >> ~/.ssh/authorized_keys"))
            append("/etc/ssh/ssh_config",
                   "\nStrictHostKeyChecking no\nUserKnownHostsFile=/dev/null",
                   use_sudo=True)
        if exec_command_after:
            run(exec_command_after)
        collect_logs(run, hostname)
        collect_logs_devstack("install_{host}".format(host=hostname))


def prepare(host, topo_config_file, devstack_config_file, apt_cacher_proxy,
            ssh_key_file, gateway,
            user, password,
            branch, repo, tempest_disable, devstack_repo, devstack_br, patch,
            quiet):
    fab_settings = {"host_string": None, "abort_on_prompts": True,
                    "gateway": gateway,
                    "user": user, "password": password, "warn_only": True}
    tempest = "" if tempest_disable else TEMPEST_CONF.format(repo=repo,
                                                             branch=branch)
    extras = os.environ.get("QA_DEVSTACK_EXTRAS", "")
    local_ssh_key_file = os.path.join(os.path.dirname(__file__), "..",
                                      "libvirt-scripts", "id_rsa")
    fab_settings.update({"key_filename": ssh_key_file or local_ssh_key_file})
    if topo_config_file:
        topo_config = yaml.load(topo_config_file)
    else:
        fab_settings.update({"host_string": host})
        topo_config = {
            'servers': {
            'devstack-server': [{"ip": host, "hostname": "devstack-server00"}]}}
    devstack_config = yaml.load(devstack_config_file)
    with open(os.path.join(DEV_CONF_PATH, "devstack_template.yaml")) as f:
        devstack_template = yaml.load(f)

    # Generate ssh-keys for new nodes
    with settings(warn_only=True, abort_on_prompts=True):
        path = os.environ.get("WORKSPACE", os.getcwd())
        warn_if_fail(local("rm {0}/id_rsa_*".format(path)))
        keys = len(topo_config['servers']['devstack-server']) or 1
        for i in range(keys):
            local("ssh-keygen -f {path}/id_rsa_{i} -t rsa -N ''".format(path=path,
                    i=topo_config['servers']['devstack-server'][i]['hostname']))
            local("cat  {path}/id_rsa_{i}.pub >> {path}/id_rsa_all.pub".format(
                path=path, i=topo_config['servers']['devstack-server'][i]['hostname']))

    # Install control node first
    control_node = topo_config['servers']['devstack-server'][0]
    fab_settings["host_string"] = control_node["ip"]
    node_devstack_config = devstack_config["servers"][0]["local_conf"].format(
        control_node_ip=control_node["ip"],
        node_ip=control_node["ip"],
        tempest=tempest)
    devstack_full_config = devstack_template["TEMPLATE"].format(
        host_specific=node_devstack_config,
        extras=extras)
    config_files = devstack_config["servers"][0].get("files", None)
    exec_commands_before = devstack_config["servers"][0].get("commands_before")
    exec_commands_after = devstack_config["servers"][0].get("commands_after")
    node_configs = {control_node["ip"]: {
        "fab_settings": fab_settings, "devstack_config": devstack_full_config,
        "hostname": control_node["hostname"], "config_files": config_files,
        "exec_commands_before": exec_commands_before,
        "exec_commands_after": exec_commands_after
    }}
    execute(install, aggregated_configs=node_configs,
            apt_cacher_proxy=apt_cacher_proxy, patch=patch,
            devstack_repo=devstack_repo, devstack_br=devstack_br, quiet=quiet,
            hosts=control_node["ip"])
    # Install other nodes in parallel
    if len(topo_config["servers"]["devstack-server"]) > 1:
        nodes = []
        node_configs = {}
        for node, conf in zip(topo_config['servers']['devstack-server'][1:],
                              devstack_config["servers"][1:]):
            fab_settings["host_string"] = node["ip"]
            node_devstack_config = conf["local_conf"].format(
                control_node_ip=control_node["ip"],
                node_ip=node['ip'], tempest=tempest)
            devstack_full_config = devstack_template["TEMPLATE"].format(
                host_specific=node_devstack_config,
                extras=extras)
            config_files = conf.get("files", None)
            exec_commands_before = conf.get("commands_before")
            exec_commands_after = conf.get("commands_after")
            nodes.append(node["ip"])
            node_configs[node["ip"]] = {"fab_settings": fab_settings,
                                        "hostname": node["hostname"],
                                        "devstack_config": devstack_full_config,
                                        "config_files": config_files,
                                        "exec_commands_before": exec_commands_before,
                                        "exec_commands_after": exec_commands_after}
        execute(install, aggregated_configs=node_configs,
                apt_cacher_proxy=apt_cacher_proxy, patch=patch,
                devstack_repo=devstack_repo, devstack_br=devstack_br,
                quiet=quiet, hosts=nodes)


def main():
    p = argparse.ArgumentParser(description=DESCRIPTION,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('-a', dest='host',
                   help='IP of host in to install Devstack on')
    p.add_argument('-b', dest='branch', nargs="?", default="ipv6", const="ipv6",
                   help='Tempest repository branch, default is ipv6')
    p.add_argument('-c', dest='config_file',
                   help='Configuration file for topology, default is None',
                   type=argparse.FileType('r'))
    p.add_argument('--devstack_config', dest='devstack_config', nargs="?",
                   const=DEVSTACK_DEFAULT, default=DEVSTACK_DEFAULT,
                   help='Configuration file for Devstack',
                   type=argparse.FileType('r'))
    p.add_argument('--apt_cacher_proxy', dest='apt_cacher_proxy', default=None,
                   help='Use proxy for apt-cache', type=argparse.FileType('r'))
    p.add_argument('-g', dest='gateway', help='Gateway to connect to host')
    p.add_argument('-q', action='store_true', default=False, dest='quiet',
                   help='Make all silently')
    p.add_argument('-k', dest='ssh_key_file',
                   help='SSH key file, default is from repo')
    p.add_argument('-j', action='store_true', dest='proxy', default=False,
                   help='Use Cisco proxy if installing from Cisco local network')
    p.add_argument('-u', dest='user', help='User to run the script with',
                   required=True)
    p.add_argument('-p', dest='password', help='Password for user and sudo',
                   required=True)
    p.add_argument('-m', dest='patch', nargs="?", const=None, default=None,
                   help='If apply patches to Devstack e.g. refs/changes/87/87987/22')
    p.add_argument('-e', dest='devstack_repo', nargs="?",
                   const=DEVSTACK_REPO, default=DEVSTACK_REPO,
                   help='Devstack repository.')
    p.add_argument('-l', dest='devstack_br', nargs="?",
                   const=DEVSTACK_BRANCH, default=DEVSTACK_BRANCH,
                   help='Devstack branch')
    p.add_argument('--disable-tempest', action='store_true', default=False,
                   dest='tempest_disable',
                   help="Don't install tempest on devstack")
    p.add_argument('-r', dest='repo', nargs="?",
                   const=CISCO_TEMPEST_REPO, default=CISCO_TEMPEST_REPO,
                   help='Tempest repository.')
    p.add_argument('--version', action='version', version='%(prog)s 2.0')
    args = p.parse_args()
    if not (args.host or args.config_file):
        raise Exception("You need to specify either host or config file")
    prepare(topo_config_file=args.config_file,
            devstack_config_file=args.devstack_config,
            host=args.host, gateway=args.gateway,
            apt_cacher_proxy=args.apt_cacher_proxy,
            ssh_key_file=args.ssh_key_file, user=args.user,
            password=args.password,
            tempest_disable=args.tempest_disable, branch=args.branch,
            repo=args.repo,
            devstack_repo=args.devstack_repo, devstack_br=args.devstack_br,
            patch=args.patch,
            quiet=args.quiet)


if __name__ == "__main__":
    main()