#!/usr/bin/env python
from StringIO import StringIO
import argparse
import os
import yaml

from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, append
from fabric.colors import green, red

from utils import warn_if_fail, quit_if_fail, update_time

__author__ = 'sshnaidm'

CISCO_TEMPEST_REPO = "https://github.com/CiscoSystems/tempest.git"
DOMAIN_NAME = "domain.name"

LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs"}

CONTROLLER = '''
[[local|localrc]]
HOST_IP={control_host_ip}
MULTI_HOST=1
disable_service n-net heat h-api h-api-cfn h-api-cw h-eng cinder c-api c-sch c-vol n-novnc
enable_service neutron q-svc q-agt q-dhcp q-l3 q-meta n-cpu q-vpn q-lbaas
{tempest}
ADMIN_PASSWORD=Cisco123
SERVICE_TOKEN=$ADMIN_PASSWORD
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
MYSQL_PASSWORD=nova
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
LOGFILE=/tmp/stack.sh.log
SCREEN_LOGDIR=/opt/stack/logs
VERBOSE=True
DEBUG=True
USE_SCREEN=True
API_RATE_LIMIT=False
IP_VERSION={ipversion}
MGMT_NET={mgmt}
FIXED_RANGE_V6=2001:dead:beef:deed::/64
IPV6_NETWORK_GATEWAY=2001:dead:beef:deed::1
REMOVE_PUBLIC_BRIDGE=False
'''
COMPUTE = '''
[[local|localrc]]
HOST_IP={compute_host_ip}
SERVICE_HOST={control_host_ip}
MYSQL_HOST={control_host_ip}
RABBIT_HOST={control_host_ip}
GLANCE_HOSTPORT={control_host_ip}:9292
MULTI_HOST=1
ADMIN_PASSWORD=Cisco123
SERVICE_TOKEN=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
MYSQL_PASSWORD=nova
ENABLED_SERVICES=n-cpu,neutron,n-api,q-agt
LIBVIRT_TYPE=qemu
NOVA_USE_QUANTUM_API=v2
VOLUME_BACKING_FILE_SIZE=2052M
LOGFILE=/tmp/stack.sh.log
SCREEN_LOGDIR=/opt/stack/logs
VERBOSE=True
DEBUG=True
USE_SCREEN=True
IP_VERSION={ipversion}
MGMT_NET={mgmt}
FIXED_RANGE_V6=2001:dead:beef:deed::/64
IPV6_NETWORK_GATEWAY=2001:dead:beef:deed::1
REMOVE_PUBLIC_BRIDGE=False
'''
ALLINONE = """[[local|localrc]]
ADMIN_PASSWORD=Cisco123
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD
SERVICE_TOKEN=1112f596-76f3-11e3-b3b2-e716f9080d50
MYSQL_PASSWORD=nova
enable_service g-api g-reg key n-api n-crt n-obj n-cpu n-cond cinder c-sch
enable_service c-api c-vol n-sch n-novnc n-xvnc n-cauth horizon rabbit
enable_service mysql q-svc q-agt q-l3 q-dhcp q-meta q-lbaas q-vpn q-fwaas q-metering neutron
disable_service n-net
{tempest}
NOVA_USE_NEUTRON_API=v2
API_RATE_LIMIT=False
VERBOSE=True
DEBUG=True
LOGFILE=~/stack.sh.log
USE_SCREEN=True
SCREEN_LOGDIR=/opt/stack/logs
IP_VERSION={ipversion}
MGMT_NET={mgmt}
IPV6_PRIVATE_RANGE=2001:dead:beef:deed::/64
IPV6_NETWORK_GATEWAY=2001:dead:beef:deed::1
REMOVE_PUBLIC_BRIDGE=False
RECLONE=True
"""


def make_local(filepath, sudo_flag, opts):
    tempest_conf = """enable_service tempest
TEMPEST_REPO={repo}
TEMPEST_BRANCH={branch}"""
    ipversion = "4+6" if opts.ipversion == 64 else str(opts.ipversion)
    mgmt = "4+6" if opts.mgmt == 64 else str(opts.mgmt)
    tempest = "" if opts.tempest_disable else tempest_conf.format(repo=opts.repo, branch=opts.branch)
    if hasattr(opts, "compute_node_ip"):
        conf = opts.local_conf.format(ipversion=ipversion, mgmt=mgmt, tempest=tempest,
                                      control_host_ip=opts.control_node_ip,
                                      compute_host_ip=opts.compute_node_ip)
    else:
        conf = opts.local_conf.format(ipversion=ipversion, mgmt=mgmt, tempest=tempest,
                                      control_host_ip=opts.control_node_ip)
    fd = StringIO(conf)
    warn_if_fail(put(fd, filepath, use_sudo=sudo_flag))


def install_devstack(settings_dict, envs=None, verbose=None, proxy=None, patch=False, opts=None):
    envs = envs or {}
    verbose = verbose or {}

    def localget(remote_path, local_path):
        if exists(remote_path):
            get(remote_path, local_path)
        else:
            print (red("No % file, something went wrong! :(" % remote_path))

    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100", use_sudo=True)
        if proxy:
            warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                             "/etc/apt/apt.conf.d/00proxy",
                             use_sudo=True))
            warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                             "/etc/apt/apt.conf.d/00no_pipelining",
                             use_sudo=True))
        update_time(sudo)
        if opts.ipversion != 4:
            sudo("/sbin/sysctl -w net.ipv6.conf.all.forwarding=1")
            append("/etc/sysctl.conf", "net.ipv6.conf.all.forwarding=1", use_sudo=True)
        warn_if_fail(sudo("apt-get update"))
        warn_if_fail(sudo("apt-get install -y git python-pip"))
        warn_if_fail(run("git config --global user.email 'test.node@example.com';"
                         "git config --global user.name 'Test Node'"))
        run("rm -rf ~/devstack")
        quit_if_fail(run("git clone https://github.com/openstack-dev/devstack.git"))
        make_local("devstack/local.conf", sudo_flag=False, opts=opts)
        with cd("devstack"):
            warn_if_fail(run("./stack.sh"))
            if patch:
                warn_if_fail(run("git fetch https://review.openstack.org/openstack-dev/devstack "
                                 "refs/changes/87/87987/12 && git format-patch -1 FETCH_HEAD"))
        if settings_dict.get("host_string") == opts.control_node_ip:
            localget('~/devstack/openrc', "./openrc")
            localget('/opt/stack/tempest/etc/tempest.conf', "./tempest.conf")
        print (green("Finished!"))
        return True


def make_job(opts):
    job = {"host_string": opts.host,
           "user": opts.user,
           "password": opts.password,
           "warn_only": True,
           "key_filename": opts.ssh_key_file,
           "abort_on_prompts": True,
           "gateway": opts.gateway}
    return job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', dest='host', default=None, help='IP of host in to install Devstack on')
    parser.add_argument('-b', dest='branch', nargs="?",
                        default="master-in-use", const="master-in-use",
                        help='Tempest repository branch, default is master-in-use')
    parser.add_argument('-c', dest='config_file', default=None,
                        help='Configuration file, default is None', type=argparse.FileType)
    parser.add_argument('-g', dest='gateway', default=None, help='Gateway to connect to host')
    parser.add_argument('-q', action='store_true', default=False, dest='quiet', help='Make all silently')
    parser.add_argument('-k', dest='ssh_key_file', default=None, help='SSH key file, default is from repo')
    parser.add_argument('-j', action='store_true', dest='proxy', default=False,
                        help='Use Cisco proxy if installing from Cisco local network')
    parser.add_argument('-u', dest='user', help='User to run the script with')
    parser.add_argument('-p', dest='password', help='Password for user and sudo')
    parser.add_argument('-m', action='store_true', default=False, dest='patch',
                        help='If apply patches to Devstack')
    parser.add_argument('--ip-version', dest='ipversion', type=int, default=4,
                        choices=[4, 6, 64], help='IP version in local.conf, default is 4')
    parser.add_argument('--mgmt-version', dest='mgmt', type=int, default=4,
                        choices=[4, 6, 64], help='MGMT net IP version, default is 4')
    parser.add_argument('--disable-tempest', action='store_true', default=False, dest='tempest_disable',
                        help="Don't install tempest on devstack")
    parser.add_argument('-r', dest='repo', nargs="?",
                        const=CISCO_TEMPEST_REPO, default=CISCO_TEMPEST_REPO,
                        help='Tempest repository, default is https://github.com/CiscoSystems/tempest.git')
    parser.add_argument('--version', action='version', version='%(prog)s 2.0')

    opts = parser.parse_args()
    actual_jobs = []
    opts.local_conf = ALLINONE
    verb_mode = []
    if opts.quiet:
        verb_mode = ['output', 'running', 'warnings']
    if not opts.ssh_key_file:
        opts.ssh_key_file = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
    if not opts.config_file:
        actual_jobs.append(make_job(opts))
    else:
        local_conf = [CONTROLLER, COMPUTE]
        config = yaml.load(opts.config_file)
        opts.control_node_ip = config['servers']['devstack-server'][0]["ip"]
        opts.compute_node_ip = config['servers']['devstack-server'][1]["ip"]
        for k, v in zip(config['servers']['devstack-server'], local_conf):
            args = opts
            args.host = k["ip"]
            args.user = args.user or k["user"]
            args.password = args.password or k["password"]
            args.local_conf = v
            actual_jobs.append(make_job(args))
    for job in actual_jobs:
        if install_devstack(settings_dict=job,
                            verbose=verb_mode,
                            proxy=opts.proxy,
                            patch=opts.patch,
                            opts=opts):
            print("Job with host {host} finished successfully!".format(host=opts.host))


if __name__ == "__main__":
    main()