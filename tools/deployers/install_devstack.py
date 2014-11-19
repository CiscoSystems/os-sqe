#!/usr/bin/env python
from StringIO import StringIO
import argparse
import os
import yaml

from fabric.api import sudo, settings, run, hide, put, cd, get, local
from fabric.contrib.files import append, exists
from utils import collect_logs, warn_if_fail, quit_if_fail, update_time

DESCRIPTION = 'Installer for Devstack.'
CISCO_TEMPEST_REPO = 'https://github.com/CiscoSystems/tempest.git'
DEVSTACK_REPO = 'https://github.com/openstack-dev/devstack.git'
DEVSTACK_BRANCH = 'master'
DOMAIN_NAME = 'domain.name'
LOGS_COPY = {"/etc": "etc_configs", "/var/log": "all_logs", "/opt/stack/stack.sh.log": "stack.sh.log"}
DEVSTACK_TEMPLATE = '''
[[local|localrc]]
ADMIN_PASSWORD=Cisco123
{services_specific}
SERVICE_TOKEN=$ADMIN_PASSWORD
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
MYSQL_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
NOVA_USE_QUANTUM_API=v3
LOGFILE=$DEST/stack.sh.log
VERBOSE=True
DEBUG=True
USE_SCREEN=True
SCREEN_LOGDIR=$DEST/logs
API_RATE_LIMIT=False
REMOVE_PUBLIC_BRIDGE=False
IMAGE_URLS='http://172.29.173.233/cirros-0.3.3-x86_64-uec.tar.gz,http://172.29.173.233/trusty-server-cloudimg-amd64-disk1.img'
CIRROS_VERSION=0.3.3
SWIFT_REPLICAS=1
SWIFT_HASH=011688b44136573e209e
{extras}
'''
CONTROLLER = '''
MULTI_HOST=True
HOST_IP={control_node_ip}
enable_service g-api g-reg key n-api n-crt n-obj n-cpu n-cond cinder c-sch
enable_service c-api c-vol n-sch n-novnc n-xvnc n-cauth horizon rabbit
enable_service mysql q-svc q-agt q-l3 q-dhcp q-meta q-lbaas q-vpn q-fwaas q-metering neutron
disable_service n-net
enable_service s-proxy s-object s-container s-account
{tempest}
'''
COMPUTE = '''
HOST_IP={compute_node_ip}
SERVICE_HOST={control_node_ip}
MYSQL_HOST={control_node_ip}
RABBIT_HOST={control_node_ip}
GLANCE_HOSTPORT={control_node_ip}:9292
ENABLED_SERVICES=n-cpu,neutron,n-api,q-agt
'''
ALLINONE = """
enable_service g-api g-reg key n-api n-crt n-obj n-cpu n-cond cinder c-sch
enable_service c-api c-vol n-sch n-novnc n-xvnc n-cauth horizon rabbit
enable_service mysql q-svc q-agt q-l3 q-dhcp q-meta q-lbaas q-vpn q-fwaas q-metering neutron
disable_service n-net
enable_service s-proxy s-object s-container s-account
{tempest}
"""
TEMPEST_CONF = """enable_service tempest
TEMPEST_REPO={repo}
TEMPEST_BRANCH={branch}"""


def install_devstack(fab_settings, string_descriptor, hostname, download_conf=False,
                     ipversion="4", patch="", proxy="", devstack_repo="", devstack_br="", quiet=False):
    verbose = []
    if quiet:
        verbose = ['output', 'running', 'warnings']
    with settings(**fab_settings), hide(*verbose):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100", use_sudo=True)
        if proxy:
            warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy", use_sudo=True))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining", use_sudo=True))
        update_time(sudo)
        if ipversion != "4":
            sudo("/sbin/sysctl -w net.ipv6.conf.all.forwarding=1")
            append("/etc/sysctl.conf", "net.ipv6.conf.all.forwarding=1", use_sudo=True)
        warn_if_fail(sudo("apt-get update"))
        warn_if_fail(sudo("apt-get install -y git python-pip"))
        warn_if_fail(run("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        if exists("devstack"):
            with cd("devstack"):
                warn_if_fail(run("./unstack.sh"))
        run("rm -rf ~/devstack")
        quit_if_fail(run("git clone -b {branch} {devstack}".format(devstack=devstack_repo,
                                                                   branch=devstack_br)))
        if patch:
            with cd("devstack"):
                warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack {patch} "
                                 "&& git cherry-pick FETCH_HEAD".format(patch=patch)))
        warn_if_fail(put(string_descriptor, "devstack/local.conf", use_sudo=False))
        with cd("devstack"):
            warn_if_fail(run("./stack.sh"))
        if download_conf:
            get('~/devstack/openrc', "./openrc")
            get('/opt/stack/tempest/etc/tempest.conf', "./tempest.conf")
        path = os.environ.get("WORKSPACE", os.getcwd())
        if os.path.exists("{path}/id_rsa_{key}".format(path=path, key=hostname)):
            path = os.environ.get("WORKSPACE", os.getcwd())
            put("{path}/id_rsa_{key}".format(path=path, key=hostname), "~/.ssh/id_rsa")
            put("{path}/id_rsa_{key}.pub".format(path=path, key=hostname), "~/.ssh/id_rsa.pub")
            put("{0}/id_rsa_all.pub".format(path), "/tmp/all_authorized")
            warn_if_fail(run("chmod 500 ~/.ssh/id_rsa"))
            warn_if_fail(run("cat /tmp/all_authorized >> ~/.ssh/authorized_keys"))
            append("/etc/ssh/ssh_config", "\nStrictHostKeyChecking no\nUserKnownHostsFile=/dev/null", use_sudo=True)
        collect_logs(run, hostname)


def install(fab_settings, branch, quiet, proxy, patch, local_conf,
            ipversion, tempest_disable, repo, hostname, devstack_repo, devstack_br, nodes=None):
    if ipversion:
        ipversion = "IP_VERSION=4+6" if ipversion == 64 else "IP_VERSION=" + str(ipversion)
    tempest = "" if tempest_disable else TEMPEST_CONF.format(repo=repo,
                                                             branch=branch)
    if nodes:
        string_descriptor = StringIO(local_conf.format(ipversion=ipversion, tempest=tempest,
                                                       control_node_ip=nodes["control_node_ip"],
                                                       compute_node_ip=nodes["compute_node_ip"]))
        if fab_settings['host_string'] == nodes["control_node_ip"]:
            install_devstack(fab_settings=fab_settings, string_descriptor=string_descriptor,
                             hostname=hostname,
                             download_conf=True, ipversion=ipversion, patch=patch,
                             proxy=proxy, devstack_repo=devstack_repo, devstack_br=devstack_br, quiet=quiet)
        else:
            install_devstack(fab_settings=fab_settings, string_descriptor=string_descriptor,
                             hostname=hostname,
                             download_conf=False, ipversion=ipversion, patch=patch,
                             proxy=proxy, devstack_repo=devstack_repo, devstack_br=devstack_br,
                             quiet=quiet)
    else:
        string_descriptor = StringIO(local_conf.format(ipversion=ipversion, tempest=tempest))
        install_devstack(fab_settings=fab_settings, string_descriptor=string_descriptor,
                         hostname=hostname,
                         download_conf=True, ipversion=ipversion,
                         patch=patch, proxy=proxy, devstack_repo=devstack_repo, devstack_br=devstack_br,
                         quiet=quiet)


def install_multinode(host, branch, config_file, gateway, quiet, ssh_key_file,
                      proxy, user, password, patch, ipversion, tempest_disable, repo,
                      devstack_repo, devstack_br):
    extras = os.environ.get("QA_DEVSTACK_EXTRAS", "")
    local_conf = [DEVSTACK_TEMPLATE.format(services_specific=ALLINONE, extras=extras)]
    fab_settings = {"host_string": None, "abort_on_prompts": True, "gateway": gateway,
                    "user": user, "password": password, "warn_only": True}
    local_ssh_key_file = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
    fab_settings.update({"key_filename": ssh_key_file or local_ssh_key_file})
    if host:
        fab_settings.update({"host_string": host})
        install(fab_settings=fab_settings, branch=branch, quiet=quiet, proxy=proxy,
                patch=patch, local_conf=local_conf[0], ipversion=ipversion, tempest_disable=tempest_disable,
                repo=repo, hostname=host, devstack_repo=devstack_repo, devstack_br=devstack_br, nodes=None)
    elif config_file:
        config = yaml.load(config_file)
        nodes = {}
        if len(config['servers']['devstack-server']) > 1:
            local_conf = [DEVSTACK_TEMPLATE.format(services_specific=CONTROLLER, extras=extras),
                          DEVSTACK_TEMPLATE.format(services_specific=COMPUTE, extras=extras)]
            nodes = {"control_node_ip": config['servers']['devstack-server'][0]['ip'],
                     "compute_node_ip": config['servers']['devstack-server'][1]['ip']}
        with settings(warn_only=True, abort_on_prompts=True):
            path = os.environ.get("WORKSPACE", os.getcwd())
            warn_if_fail(local("rm {0}/id_rsa_*".format(path)))
            keys = len(nodes) or 1
            for i in range(keys):
                local("ssh-keygen -f {path}/id_rsa_{i} -t rsa -N ''".format(path=path, i=config['servers']['devstack-server'][i]['hostname']))
                local("cat  {path}/id_rsa_{i}.pub >> {path}/id_rsa_all.pub".format(path=path, i=config['servers']['devstack-server'][i]['hostname']))
        for node, conf in zip(config['servers']['devstack-server'], local_conf):
            fab_settings.update({"host_string": node['ip']})
            install(fab_settings=fab_settings, branch=branch, quiet=quiet, proxy=proxy,
                    patch=patch, local_conf=conf, ipversion=ipversion, tempest_disable=tempest_disable,
                    repo=repo, hostname=node['hostname'], nodes=nodes, devstack_repo=devstack_repo,
                    devstack_br=devstack_br)
    else:
        return


def define_cli(p):
    p.add_argument('-a', dest='host', help='IP of host in to install Devstack on')
    p.add_argument('-b', dest='branch', nargs="?", default="ipv6", const="ipv6",
                   help='Tempest repository branch, default is ipv6')
    p.add_argument('-c', dest='config_file',
                   help='Configuration file, default is None', type=argparse.FileType('r'))
    p.add_argument('-g', dest='gateway', help='Gateway to connect to host')
    p.add_argument('-q', action='store_true', default=False, dest='quiet', help='Make all silently')
    p.add_argument('-k', dest='ssh_key_file', help='SSH key file, default is from repo')
    p.add_argument('-j', action='store_true', dest='proxy', default=False,
                   help='Use Cisco proxy if installing from Cisco local network')
    p.add_argument('-u', dest='user', help='User to run the script with', required=True)
    p.add_argument('-p', dest='password', help='Password for user and sudo', required=True)
    p.add_argument('-m', dest='patch', nargs="?", const=None, default=None,
                   help='If apply patches to Devstack e.g. refs/changes/87/87987/22')
    p.add_argument('-e', dest='devstack_repo', nargs="?",
                   const=DEVSTACK_REPO, default=DEVSTACK_REPO,
                   help='Devstack repository.')
    p.add_argument('-l', dest='devstack_br', nargs="?",
                   const=DEVSTACK_BRANCH, default=DEVSTACK_BRANCH,
                   help='Devstack branch')
    p.add_argument('--ip-version', dest='ipversion', default="",
                   choices=[4, 6, 64], help='Explicit IP version in local.conf')
    p.add_argument('--disable-tempest', action='store_true', default=False, dest='tempest_disable',
                   help="Don't install tempest on devstack")
    p.add_argument('-r', dest='repo', nargs="?",
                   const=CISCO_TEMPEST_REPO, default=CISCO_TEMPEST_REPO,
                   help='Tempest repository.')
    p.add_argument('--version', action='version', version='%(prog)s 2.0')

    def main_with_args(args):
        install_multinode(host=args.host, branch=args.branch, config_file=args.config_file,
                          gateway=args.gateway, quiet=args.quiet, ssh_key_file=args.ssh_key_file,
                          proxy=args.proxy, user=args.user, password=args.password, patch=args.patch,
                          ipversion=args.ipversion, tempest_disable=args.tempest_disable,
                          repo=args.repo, devstack_repo=args.devstack_repo, devstack_br=args.devstack_br)

    p.set_defaults(func=main_with_args)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=DESCRIPTION,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    define_cli(p)
    args = p.parse_args()
    args.func(args)
