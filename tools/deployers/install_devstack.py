#!/usr/bin/env python
from StringIO import StringIO
import argparse
import sys
import yaml
import os

from fabric.api import sudo, settings, run, hide, put, shell_env, local, cd, get
from fabric.contrib.files import exists, contains, append, sed
from fabric.colors import green, red, yellow

from workarounds import fix_aio as fix
from utils import collect_logs, dump, all_servers, quit_if_fail, warn_if_fail, update_time, resolve_names, CONFIG_PATH, \
    LOGS_COPY, change_ip_to

__author__ = 'sshnaidm'

DOMAIN_NAME = "domain.name"
APPLY_LIMIT = 3
# override logs dirs if you need
LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs",
    "/etc/puppet": "puppet_configs",
}

SERVICES = ['neutron-', 'nova', 'glance', 'cinder', 'keystone']


def apply_changes():
    warn_if_fail(run("./unstack.sh"))
    kill_services()
    apply_patches()
    warn_if_fail(run("./stack.sh"))


def apply_patches():
    warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
    "refs/changes/87/87987/12 && git format-patch -1  FETCH_HEAD"))
    
    #warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
    #"refs/changes/23/97823/1 && git format-patch -1  FETCH_HEAD"))

def kill_services():
    func_run = sudo
    for service in SERVICES:
        func_run("pkill -f %s" % service)
    func_run("rm -rf /var/lib/dpkg/lock")
    func_run("rm -rf /var/log/libvirt/libvirtd.log")

def make_local(filepath, sudo_flag):
    conf = """[[local|localrc]]
ADMIN_PASSWORD=secret
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
MYSQL_PASSWORD=nova
ENABLED_SERVICES=g-api,g-reg,key,n-api,n-crt,n-obj,n-cpu,n-cond,cinder,c-sch,c-api,c-vol,n-sch,n-novnc,n-xvnc,n-cauth,horizon,rabbit
enable_service mysql
disable_service n-net
enable_service q-svc
enable_service q-agt
enable_service q-l3
enable_service q-dhcp
enable_service q-meta
enable_service q-lbaas
enable_service neutron
enable_service tempest
NOVA_USE_NEUTRON_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=/tmp/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/logs
TEMPEST_REPO=https://github.com/kshileev/tempest.git
TEMPEST_BRANCH=ipv6
#RECLONE=no
#OFFLINE=True
"""
    fd = StringIO(conf)
    warn_if_fail(put(fd, filepath, use_sudo=sudo_flag))





def install_openstack(settings_dict, envs=None, verbose=None, prepare=False, proxy=None, config=None):
    """
    Install OS with COI with script provided by Chris on any host(s)

    :param settings_dict: settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    :param url_script: URl of Cisco installer script from Chris
    :return: always true
    """
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run

    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        if proxy:
            warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy",
                             use_sudo=use_sudo_flag))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining",
                             use_sudo=use_sudo_flag))
        update_time(run_func)
        warn_if_fail(run_func("apt-get update"))
        warn_if_fail(run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                              '-o Dpkg::Options::="--force-confdef" -o '
                              'Dpkg::Options::="--force-confold" dist-upgrade'))
        warn_if_fail(run_func("apt-get install -y git python-pip"))
        warn_if_fail(run("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        warn_if_fail(sed("/etc/hosts", "127.0.1.1.*",
                         "127.0.1.1 all-in-one all-in-one.domain.name", use_sudo=use_sudo_flag))
        warn_if_fail(put(StringIO("all-in-one"), "/etc/hostname", use_sudo=use_sudo_flag))
        warn_if_fail(run_func("hostname all-in-one"))
        if prepare:
            return True
        else:
            warn_if_fail(run("git clone https://github.com/openstack-dev/devstack.git"))
            make_local("devstack/local.conf", sudo_flag=False)
            with cd("devstack"):
                warn_if_fail(run("./stack.sh"))
                apply_changes()

        if exists('~/devstack/openrc'):
            get('~/devstack/openrc', "./openrc")
        else:
            print (red("No openrc file, something went wrong! :("))
    print (green("Finished!"))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store', dest='user',
                        help='User to run the script with')
    parser.add_argument('-p', action='store', dest='password',
                        help='Password for user and sudo')
    parser.add_argument('-a', action='append', dest='hosts', default=[],
                        help='List of hosts for action')
    parser.add_argument('-g', action='store', dest='gateway', default=None,
                        help='Gateway to connect to host')
    parser.add_argument('-q', action='store_true', default=False, dest='quiet',
                        help='Make all silently')
    parser.add_argument('-x', action='store', default="eth1", dest='external_interface',
                        help='External interface: eth0, eth1... default=eth1')
    parser.add_argument('-d', action='store', default="eth0", dest='default_interface',
                        help='Default interface: eth0, eth1... default=eth0')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default=None,
                        help='SSH key file, default is from repo')
    parser.add_argument('-z', action='store_true', dest='prepare_mode', default=False,
                        help='Only prepare, don`t run the main script')
    parser.add_argument('-j', action='store_true', dest='proxy', default=False,
                        help='Use cisco proxy if installing from Cisco local network')
    parser.add_argument('-c', action='store', dest='config_file', default=None,
                        help='Configuration file, default is None')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    opts = parser.parse_args()
    if opts.quiet:
        verb_mode = ['output', 'running', 'warnings']
    else:
        verb_mode = []
    path2ssh = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
    ssh_key_file = opts.ssh_key_file if opts.ssh_key_file else path2ssh
    if not opts.config_file:
        envs_aio = {"default_interface": opts.default_interface,
                    "external_interface": opts.default_interface}
        hosts = opts.hosts
        user = opts.user
        password = opts.password
        config = None
    else:
        try:
            with open(opts.config_file) as f:
                config = yaml.load(f)
        except IOError as e:
            print >> sys.stderr, "Not found file {file}: {exc}".format(file=opts.config_file, exc=e)
            sys.exit(1)
        aio = config['servers']['aio']
        hosts = [aio["ip"]]
        user = opts.user
        password = opts.password
        envs_aio = {"default_interface": aio["default_interface"],
                    "external_interface": aio["external_interface"]}

    job_settings = {"host_string": "",
                    "user": user,
                    "password": password,
                    "warn_only": True,
                    "key_filename": ssh_key_file,
                    "abort_on_prompts": True,
                    "gateway": opts.gateway}
    for host in hosts:
        job_settings['host_string'] = host
        print >> sys.stderr, job_settings
        print >> sys.stderr, envs_aio
        res = install_openstack(job_settings,
                                verbose=verb_mode,
                                envs=envs_aio,
                                prepare=opts.prepare_mode,
                                proxy=opts.proxy)
        if res:
            print "Job with host {host} finished successfully!".format(host=host)


if __name__ == "__main__":
    main()
