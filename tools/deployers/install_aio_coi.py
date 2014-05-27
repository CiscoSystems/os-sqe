#!/usr/bin/env python
from StringIO import StringIO
import urllib2
import argparse
import sys
from fabric.api import sudo, settings, run, hide, put, shell_env, cd
from fabric.contrib.files import sed

__author__ = 'sshnaidm'


def install_openstack(settings_dict, envs=None, verbose=None, url_script=None):
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
    response = urllib2.urlopen(url_script)
    install_script = response.read()
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run

    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        # TODO: check statuses of commands
        apt_update = run_func("apt-get update")
        apt_install = run_func("apt-get install -y git")
        run1 = run_func("git config --global user.email 'test.node@example.com';"
                        "git config --global user.name 'Test Node'")
        sed1 = sed("/etc/hosts", "127.0.1.1.*",
                   "127.0.1.1 all-in-one all-in-one.domain.name", use_sudo=use_sudo_flag)
        put(StringIO("all-in-one"), "/etc/hostname", use_sudo=use_sudo_flag)
        res2 = run_func("hostname all-in-one")
        put(StringIO(install_script), "/root/install_icehouse_cisco.sh", use_sudo=use_sudo_flag)
        with cd("/root/"):
            res_install = run_func("/bin/bash /root/install_icehouse_cisco.sh")
        print "Finished!"
        return True


def run_probe(settings_dict, envs=None, verbose=None):
    """
    Before installing OS check connectivity and executing with this function on remote host

    :param settings_dict:  settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    :return: response code of executed command or 1 if exception
    """
    envs = envs or {}
    verbose = verbose or []
    try:
        with settings(**settings_dict), hide(*verbose), shell_env(**envs):
            res = run("ls /tmp/")
    except Exception as e:
        print "Exception: ", e
        return 1
    return res.return_code


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
    parser.add_argument('-l', action='store',
                        default=("https://gist.githubusercontent.com/rickerc/9836426/raw/9180564661002da6faab52"
                                 "6d4a69db53bbfccde7/install_icehouse_cisco.sh"),
                        dest='url',
                        help='Url from where to download COI installer')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default='~/.ssh/id_rsa',
                        help='SSH key file, default=~/.ssh/id_rsa')
    parser.add_argument('-t', action='store_true', dest='test_mode', default=False,
                        help='Just run it to test host connectivity, if fine - return 0')
    parser.add_argument('-c', action='store', dest='config_file', default=None,
                        help='Configuration file, default is None')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    opts = parser.parse_args()
    if not opts.config_file:
        envs_aio = {"default_interface": opts.default_interface,
                    "external_interface": opts.default_interface}
        if opts.quiet:
            verb_mode = ['output', 'running', 'warnings']
        else:
            verb_mode = []
        hosts = opts.hosts
    else:
        # TODO: parse config here
        pass
    job_settings = {"host_string": "",
                    "user": opts.user,
                    "password": opts.password,
                    "warn_only": True,
                    "key_filename": opts.ssh_key_file,
                    "abort_on_prompts": True,
                    "gateway": opts.gateway}
    if opts.test_mode:
        job_settings['host_string'] = hosts[0]
        job_settings['command_timeout'] = 15
        sys.exit(run_probe(job_settings, verbose=verb_mode, envs=envs_aio))
    for host in hosts:
        job_settings['host_string'] = host
        print job_settings
        res = install_openstack(job_settings, verbose=verb_mode, envs=envs_aio, url_script=opts.url)
        if not res:
            print "Job with host {host} finished successfully!".format(host=host)

if __name__ == "__main__":
    main()
