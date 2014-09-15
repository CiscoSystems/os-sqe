#!/usr/bin/env python
from tempfile import NamedTemporaryFile
import argparse
import itertools
import os
import yaml

from ConfigParser import SafeConfigParser
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, append, contains
from fabric.colors import green, red

from utils import warn_if_fail, update_time, collect_logs


DOMAIN_NAME = "domain.name"
# override logs dirs if you need
LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs",
}


def prepare_answers(path, topo, config):
    with NamedTemporaryFile() as temp:
        warn_if_fail(get(path, temp.name))
        temp.flush()
        parser = SafeConfigParser()
        parser.optionxform = str
        parser.read(temp.name)
    parser.set("general", "CONFIG_PROVISION_DEMO", "y")
    parser.set("general", "CONFIG_PROVISION_TEMPEST", "y")
    parser.set("general", "CONFIG_PROVISION_TEMPEST_REPO_REVISION", "master")
    parser.set("general", "CONFIG_KEYSTONE_ADMIN_PW", "Cisco123")
    parser.set("general", "CONFIG_KEYSTONE_DEMO_PW", "secret")
    parser.set("general", "CONFIG_DEBUG_MODE", "y")
    parser.set("general", "CONFIG_NTP_SERVERS", "10.81.254.202,ntp.esl.cisco.com")
    parser.set("general", "CONFIG_NOVA_NETWORK_DEFAULTFLOATINGPOOL", "public")
    if topo == "2role":
        parser.set("general", "CONFIG_CONTROLLER_HOST", config['servers']['control-server'][0]['ip'])
        parser.set("general", "CONFIG_COMPUTE_HOSTS", config['servers']['compute-server'][0]['ip'])
    if topo == "3role":
        parser.set("general", "CONFIG_CONTROLLER_HOST", config['servers']['build-server'][0]['ip'])
        parser.set("general", "CONFIG_NETWORK_HOSTS", config['servers']['control-server'][0]['ip'])
        parser.set("general", "CONFIG_COMPUTE_HOSTS", config['servers']['compute-server'][0]['ip'])
    with open("installed_answers", "w") as f:
        parser.write(f)
    warn_if_fail(put("installed_answers", "~/installed_answers"))


def prepare_for_install(settings_dict,
                     envs=None,
                     verbose=None,
                     proxy=None,
                     key=None):
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        if exists("/etc/gai.conf"):
            append("/etc/gai.conf", "precedence ::ffff:0:0/96  100", use_sudo=use_sudo_flag)
        warn_if_fail(run_func("yum -y update"))
        warn_if_fail(run_func("yum -y install -y git python-pip vim ntpdate patch"))
        update_time(run_func)
        warn_if_fail(run_func("ssh-keygen -f ~/.ssh/id_rsa -t rsa -N ''"))
        warn_if_fail(run_func("cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys"))
        append("/etc/ssh/ssh_config",
               "\nStrictHostKeyChecking no\nUserKnownHostsFile=/dev/null",
               use_sudo=use_sudo_flag)
        #warn_if_fail(run_func("/bin/systemctl stop  NetworkManager.service"))
        #warn_if_fail(run_func("/bin/systemctl disable NetworkManager.service"))
        append("~/.bashrc", "export TERM=xterm")
        if key:
            warn_if_fail(run_func("echo '%s' >> ~/.ssh/authorized_keys" % key))
        return run_func("cat ~/.ssh/id_rsa.pub")

def install_devstack(settings_dict,
                     envs=None,
                     verbose=None,
                     proxy=None,
                     topo=None,
                     config=None):
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        warn_if_fail(run_func("yum install -y http://rdo.fedorapeople.org/rdo-release.rpm"))
        warn_if_fail(run_func("yum install -y openstack-packstack"))

        warn_if_fail(run_func("packstack --gen-answer-file=~/answers.txt"))
        prepare_answers("~/answers.txt", topo=topo, config=config)
        # Workaround for Centos 7
        if contains("/etc/redhat-release", "CentOS Linux release 7"):
            patch = os.path.join(os.path.dirname(__file__), "centos7.patch")
            warn_if_fail(put(patch, "~/centos7.patch"))
            with cd("/usr/share/openstack-puppet"):
                run_func("patch -p1 < ~/centos7.patch")
        run_func("packstack --answer-file=~/installed_answers")
        run_func("iptables -D INPUT -j REJECT --reject-with icmp-host-prohibited")
        if exists('~/keystonerc_admin'):
            get('~/keystonerc_admin', "./openrc")
        else:
            print (red("No openrc file, something went wrong! :("))
        if exists('~/keystonerc_demo'):
            get('~/keystonerc_demo', "./openrc_demo")
        if exists('~/packstack-answers-*'):
            get('~/packstack-answers-*', ".")
        collect_logs(run_func=run_func, hostname='build_box', clean=True)
        print (green("Finished!"))
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store', dest='user',
                        help='User to run the script with')
    parser.add_argument('-p', action='store', dest='password',
                        help='Password for user and sudo')
    parser.add_argument('-a', action='store', dest='host', default=None,
                        help='IP of host in to install Devstack on')
    parser.add_argument('-g', action='store', dest='gateway', default=None,
                        help='Gateway to connect to host')
    parser.add_argument('-q', action='store_true', default=False, dest='quiet',
                        help='Make all silently')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default=None,
                        help='SSH key file, default is from repo')
    parser.add_argument('-j', action='store_true', dest='proxy', default=False,
                        help='Use cisco proxy if installing from Cisco local network')
    parser.add_argument('-c', action='store', dest='config_file', default=None,
                        help='Configuration file, default is None')
    parser.add_argument('-t', action='store', dest='topology', default=None,
                        choices=["aio", "2role", "3role"],
                        help='Choose topology')
    parser.add_argument('--version', action='version', version='%(prog)s 2.0')

    opts = parser.parse_args()
    if opts.quiet:
        verb_mode = ['output', 'running', 'warnings']
    else:
        verb_mode = []
    path2ssh = os.path.join(os.path.dirname(__file__), "..", "libvirt-scripts", "id_rsa")
    ssh_key_file = opts.ssh_key_file if opts.ssh_key_file else path2ssh

    if not opts.config_file:
        root_job = {"host_string": opts.host,
               "user": opts.user,
               "password": opts.password,
               "warn_only": True,
               "key_filename": ssh_key_file,
               "abort_on_prompts": True,
               "gateway": opts.gateway}
    else:
        with open(opts.config_file) as f:
            config = yaml.load(f)

        root_key = None
        for index, box in enumerate(sorted(
                itertools.chain(*config['servers'].itervalues()),
                key=lambda x: x['ip'])):
            job = {"host_string": box["ip"],
                   "user": opts.user or box["user"],
                   "password": opts.password or box["password"],
                   "warn_only": True,
                   "key_filename": ssh_key_file,
                   "abort_on_prompts": True,
                   "gateway": opts.gateway or None}

            res = prepare_for_install(settings_dict=job,
                                      envs=None,
                                      verbose=verb_mode,
                                      proxy=opts.proxy,
                                      key=root_key)
            if index == 0:
                root_key = res
                root_job = job
            print "Prepare host {host} finished successfully!".format(
                host=job["host_string"])
    install_devstack(settings_dict=root_job,
                     envs=None,
                     verbose=verb_mode,
                     proxy=opts.proxy,
                     topo=opts.topology,
                     config=config)
    print "Job with host {host} finished successfully!".format(
        host=root_job["host_string"])


if __name__ == "__main__":
    main()
