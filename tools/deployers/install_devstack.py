#!/usr/bin/env python
from StringIO import StringIO
import argparse
import logging
import os
import yaml

from fabric.api import sudo, settings, run, hide, put, cd, get
from fabric.contrib.files import append, exists
from utils import warn_if_fail, quit_if_fail, update_time

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger = logging.getLogger(__file__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

DESCRIPTION='Installer for Devstack.'
CISCO_TEMPEST_REPO = 'https://github.com/CiscoSystems/tempest.git'
DOMAIN_NAME = 'domain.name'
LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs"}

DEVSTACK_TEMPLATE = '''
[[local|localrc]]
ADMIN_PASSWORD=Cisco123
{services_specific}
NOVA_USE_QUANTUM_API=v3
LOGFILE=$DEST/stack.sh.log
VERBOSE=True
DEBUG=True
USE_SCREEN=True
SCREEN_LOGDIR=$DEST/logs
API_RATE_LIMIT=False
FIXED_RANGE_V6=2001:dead:beef:deed::/64
IPV6_NETWORK_GATEWAY=2001:dead:beef:deed::1
REMOVE_PUBLIC_BRIDGE=False
'''
CONTROLLER = '''
MULTI_HOST=True
HOST_IP={control_node_ip}
disable_service n-net heat h-api h-api-cfn h-api-cw h-eng c-api c-sch c-vol n-novnc
enable_service neutron q-svc q-agt q-dhcp q-l3 q-meta n-cpu q-vpn q-lbaas cinder
{tempest}
SERVICE_TOKEN=$ADMIN_PASSWORD
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
MYSQL_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
IP_VERSION={ipversion}
'''
COMPUTE = '''
HOST_IP={compute_node_ip}
SERVICE_HOST={control_node_ip}
MYSQL_HOST={control_node_ip}
RABBIT_HOST={control_node_ip}
GLANCE_HOSTPORT={control_node_ip}:9292
SERVICE_TOKEN=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
MYSQL_PASSWORD=$ADMIN_PASSWORD
ENABLED_SERVICES=n-cpu,neutron,n-api,q-agt
IP_VERSION={ipversion}
'''
ALLINONE = """[[local|localrc]]
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
MYSQL_PASSWORD=$ADMIN_PASSWORD
enable_service g-api g-reg key n-api n-crt n-obj n-cpu n-cond cinder c-sch
enable_service c-api c-vol n-sch n-novnc n-xvnc n-cauth horizon rabbit
enable_service mysql q-svc q-agt q-l3 q-dhcp q-meta q-lbaas q-vpn q-fwaas q-metering neutron
disable_service n-net
{tempest}
IPV6_PRIVATE_RANGE=2001:dead:beef:deed::/64
"""
TEMPEST_CONF = """enable_service tempest
TEMPEST_REPO={repo}
TEMPEST_BRANCH={branch}"""


def install_devstack(fab_settings, fd, download_conf=False, ipversion=4, patch=False, proxy=False, verbose=None):
    logger.debug("Starting installation for next fabric settings: %s" % fab_settings)
    with settings(**fab_settings), hide(*verbose):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100", use_sudo=True)
        if proxy:
            warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy", use_sudo=True))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining", use_sudo=True))
        update_time(sudo)
        if ipversion != 4:
            sudo("/sbin/sysctl -w net.ipv6.conf.all.forwarding=1")
            append("/etc/sysctl.conf", "net.ipv6.conf.all.forwarding=1", use_sudo=True)
        warn_if_fail(sudo("apt-get update"))
        warn_if_fail(sudo("apt-get install -y git python-pip"))
        warn_if_fail(run("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        run("rm -rf ~/devstack")
        quit_if_fail(run("git clone https://github.com/openstack-dev/devstack.git"))
        if patch:
            warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
                             "refs/changes/87/87987/22 && git cherry-pick FETCH_HEAD"))
        warn_if_fail(put(fd, "devstack/local.conf", use_sudo=False))
        with cd("devstack"):
            warn_if_fail(run("./stack.sh"))
        if download_conf:
            get('~/devstack/openrc', "./openrc")
            get('/opt/stack/tempest/etc/tempest.conf', "./tempest.conf")
    logger.info("Installation in node finished!")


def install(fab_settings, stack_options):
    verbose = {}
    if stack_options.get('quiet', False):
        verbose = ['output', 'running', 'warnings']
    ipversion = "4+6" if stack_options["ipversion"] == 64 else str(stack_options["ipversion"])
    tempest = "" if stack_options.get("tempest_disable") else TEMPEST_CONF.format(repo=stack_options["repo"],
                                                                                  branch=stack_options["branch"])
    if stack_options.get('nodes', False):
        fd = StringIO(stack_options["local_conf"][0].format(ipversion=ipversion, tempest=tempest,
                                                            control_node_ip=stack_options["nodes"]["control_node_ip"],
                                                            compute_node_ip=stack_options["nodes"]["compute_node_ip"]))
        logger.debug("Devstack node configuration: %s" % fd.getvalue())
        if fab_settings['host_string'] == stack_options["nodes"]["control_node_ip"]:
            install_devstack(fab_settings, fd, True, stack_options["ipversion"],
                             stack_options["patch"], stack_options["proxy"], verbose)
        else:
            install_devstack(fab_settings, fd, False, stack_options["ipversion"],
                             stack_options["patch"], stack_options["proxy"], verbose)
    else:
        fd = StringIO(stack_options['local_conf'][0].format(ipversion=ipversion, tempest=tempest))
        logger.debug("Devstack node configuration: %s" % fd)
        install_devstack(fab_settings, fd, True, stack_options["ipversion"],
                         stack_options["patch"], stack_options["proxy"], verbose)


def main(**kwargs):
    logger.info("Running Devstack Installer with args %s" % kwargs)
    local_conf = [DEVSTACK_TEMPLATE.format(services_specific=ALLINONE)]
    fab_settings = {"host_string": None, "abort_on_prompts": True,
                    "user": kwargs['user'], "password": kwargs['password'], "warn_only": True, }
    ssh_key_file = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
    fab_settings.update({"key_filename": ssh_key_file or kwargs["ssh_key_file"]})
    if kwargs['host']:
        # If defined host will used only CLI args
        fab_settings.update({"host_string": kwargs['host']})
        kwargs.update({"local_conf": local_conf})
        install(fab_settings=fab_settings, stack_options=kwargs)
    elif kwargs.get("config_file", False):
        # If defined config file will used info from file
        config = yaml.load(kwargs.get("config_file"))
        if len(config['servers']['devstack-server']) > 1:
            # Multi node topology
            local_conf = [DEVSTACK_TEMPLATE.format(services_specific=CONTROLLER),
                          DEVSTACK_TEMPLATE.format(services_specific=COMPUTE)]
            nodes = {"control_node_ip": config['servers']['devstack-server'][0]['ip'],
                     "compute_node_ip": config['servers']['devstack-server'][1]['ip']}
            kwargs.update({"local_conf": local_conf,
                           "nodes": nodes})
            # Install Devstack for each node
            for node, conf in zip(config['servers']['devstack-server'], local_conf):
                fab_settings.update({"host_string": node['ip']})
                kwargs.update({"local_conf": [conf]})
                install(fab_settings=fab_settings, stack_options=kwargs)
        else:
            # Single node topology
            fab_settings.update({"host_string": config['servers']['devstack-server'][0]['ip']})
            kwargs.update({"local_conf": local_conf})
            install(fab_settings=fab_settings, stack_options=kwargs)
    else:
        logger.error("Devstack is not installed, no host or config file provided.")
        return
    logger.info("Devstack Installer finished successfully.")


def define_cli(p):
    p.add_argument('-a', dest='host', help='IP of host in to install Devstack on')
    p.add_argument('-b', dest='branch', nargs="?", default="master-in-use", const="master-in-use",
                   help='Tempest repository branch, default is master-in-use')
    p.add_argument('-c', dest='config_file',
                   help='Configuration file, default is None', type=argparse.FileType('r'))
    p.add_argument('-g', dest='gateway', help='Gateway to connect to host')
    p.add_argument('-q', action='store_true', default=False, dest='quiet', help='Make all silently')
    p.add_argument('-k', dest='ssh_key_file', help='SSH key file, default is from repo')
    p.add_argument('-j', action='store_true', dest='proxy', default=False,
                   help='Use Cisco proxy if installing from Cisco local network')
    p.add_argument('-u', dest='user', help='User to run the script with', required=True)
    p.add_argument('-p', dest='password', help='Password for user and sudo', required=True)
    p.add_argument('-m', action='store_true', default=False, dest='patch',
                   help='If apply patches to Devstack')
    p.add_argument('--ip-version', dest='ipversion', type=int, default=4,
                   choices=[4, 6, 64], help='IP version in local.conf, default is 4')
    p.add_argument('--disable-tempest', action='store_true', default=False, dest='tempest_disable',
                   help="Don't install tempest on devstack")
    p.add_argument('-r', dest='repo', nargs="?",
                   const=CISCO_TEMPEST_REPO, default=CISCO_TEMPEST_REPO,
                   help='Tempest repository.')
    p.add_argument('--version', action='version', version='%(prog)s 2.0')

    def main_with_args(args):
        main(host=args.host, branch=args.branch, config_file=args.config_file,
             gateway=args.gateway, quiet=args.quiet, ssh_key_file=args.ssh_key_file,
             proxy=args.proxy, user=args.user, password=args.password, patch=args.patch,
             ipversion=args.ipversion, tempest_disable=args.tempest_disable,
             repo=args.repo)

    p.set_defaults(func=main_with_args)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=DESCRIPTION,
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    define_cli(p)
    args = p.parse_args()
    args.func(args)