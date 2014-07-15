#!/usr/bin/env python
from StringIO import StringIO
import os
import argparse
import sys
import yaml

from fabric.api import sudo, settings, run, hide, put, shell_env, local, cd, get
from fabric.contrib.files import sed, append, exists
from fabric.colors import green, red, yellow
import time
from utils import collect_logs, warn_if_fail, quit_if_fail

from workarounds import fix_aio as fix


__author__ = 'sshnaidm'

APPLY_LIMIT = 3

def install_openstack(settings_dict, envs=None, verbose=None, url_script=None, prepare=False, force=False):
    """
    Install OS with COI with script provided by Chris on any host(s)

    :param settings_dict: settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    :param url_script: URl of Cisco installer script from Chris
    :param force: Use if you don't connect via interface you gonna bridge later
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
        # TODO: check statuses of commands
        with cd("/root/"):
            warn_if_fail(run_func("apt-get update"))
            ## avoid grub and other prompts
            warn_if_fail(run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                                  '-o Dpkg::Options::="--force-confdef" -o '
                                  'Dpkg::Options::="--force-confold" dist-upgrade'))
            warn_if_fail(run_func("apt-get install -y git"))
            warn_if_fail(run_func("git config --global user.email 'test.node@example.com';"
                                  "git config --global user.name 'Test Node'"))
            warn_if_fail(sed("/etc/hosts", "127.0.1.1.*",
                             "127.0.1.1 all-in-one all-in-one.domain.name", use_sudo=use_sudo_flag))
            warn_if_fail(put(StringIO("all-in-one"), "/etc/hostname", use_sudo=use_sudo_flag))
            warn_if_fail(run_func("hostname all-in-one"))
            if use_sudo_flag:
                append("/etc/sudoers",
                       "{user} ALL=(ALL) NOPASSWD: ALL".format(user=settings_dict['user']),
                       use_sudo=True)
            with cd("/root"):
                    warn_if_fail(run_func("git clone -b icehouse "
                                          "https://github.com/CiscoSystems/puppet_openstack_builder"))
            # Create another interface with different network and connect with it
            if not force and not prepare:
                with cd("puppet_openstack_builder"):
                    ## run the latest, not i.0 release
                    sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
                        "icehouse/snapshots/i.0",
                        "icehouse-proposed", use_sudo=use_sudo_flag)
                    with cd("install-scripts"):
                        result = run_func("./install.sh")
                        tries = 1
                        error = "Error:"
                        while error in result and tries <= APPLY_LIMIT:
                            time.sleep(60)
                            print >> sys.stderr, "Some errors found, running apply again"
                            result = run_func('puppet apply -v /etc/puppet/manifests/site.pp', pty=False)
                            tries += 1
                if exists('/root/openrc'):
                    get('/root/openrc', "./openrc")
                else:
                    print (red("No openrc file, something went wrong! :("))
                print (green("Copying logs and configs"))
                collect_logs(run_func=run_func, hostname="aio", clean=True)
                print (green("Finished!"))
                return True
    if force and not prepare:
        shell_envs = ";".join(["export " + k + "=" + v for k, v in envs.iteritems()]) or ""
        sudo_mode = "sudo " if use_sudo_flag else ''
        if not settings_dict['gateway']:
            local("{shell_envs}; ssh -t -t -i {id_rsa} {user}@{host} \
             '/bin/bash /root/install_icehouse_cisco.sh'".format(
                shell_envs=shell_envs,
                id_rsa=settings_dict['key_filename'],
                user=settings_dict['user'],
                host=settings_dict['host_string']))
            local("scp -i {id_rsa} {user}@{host}:/root/openrc ./openrc".format(
                id_rsa=settings_dict['key_filename'],
                user=settings_dict['user'],
                host=settings_dict['host_string']))
        else:
            local('ssh -t -t -i {id_rsa} {user}@{gateway} \
             "{shell_envs}; ssh -t -t -i {id_rsa} {user}@{host} \
             \'{sudo_mode}/bin/bash /root/install_icehouse_cisco.sh\'"'.format(
                shell_envs=shell_envs,
                id_rsa=settings_dict['key_filename'],
                user=settings_dict['user'],
                host=settings_dict['host_string'],
                gateway=settings_dict['gateway'],
                sudo_mode=sudo_mode))
            local('scp -Cp -o "ProxyCommand ssh {user}@{gateway} '
                  'nc {host} 22" root@{host}:/root/openrc ./openrc'.format(
                      user=settings_dict['user'],
                      host=settings_dict['host_string'],
                      gateway=settings_dict['gateway'],
                  ))
    print (green("Finished!"))
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
                        default=("https://gist.githubusercontent.com/rickerc/9836426/raw/69c8d28da8bd14"
                                 "ff1b295b97ed777f2544d5424b/install_icehouse_cisco.sh"),
                        dest='url',
                        help='Url from where to download COI installer')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default=None,
                        help='SSH key file, default is from repo')
    parser.add_argument('-t', action='store_true', dest='test_mode', default=False,
                        help='Just run it to test host connectivity, if fine - return 0')
    parser.add_argument('-z', action='store_true', dest='prepare_mode', default=False,
                        help='Only prepare, don`t run the main script')
    parser.add_argument('-f', action='store_true', dest='force', default=False,
                        help='Force SSH client run. Use it if dont work')
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
    else:
        with open(opts.config_file) as f:
            config = yaml.load(f)
        aio = config['servers']['aio']
        hosts = [aio["ip"]]
        user = aio["user"]
        password = aio["password"]
        envs_aio = {"default_interface": aio["default_interface"],
                    "external_interface": aio["external_interface"]}

    job_settings = {"host_string": "",
                    "user": user,
                    "password": password,
                    "warn_only": True,
                    "key_filename": ssh_key_file,
                    "abort_on_prompts": True,
                    "gateway": opts.gateway}
    if opts.test_mode:
        job_settings['host_string'] = hosts[0]
        job_settings['command_timeout'] = 15
        sys.exit(run_probe(job_settings, verbose=verb_mode, envs=envs_aio))
    for host in hosts:
        job_settings['host_string'] = host
        print job_settings
        res = install_openstack(job_settings,
                                verbose=verb_mode,
                                envs=envs_aio,
                                url_script=opts.url,
                                prepare=opts.prepare_mode,
                                force=opts.force)
        if res:
            print "Job with host {host} finished successfully!".format(host=host)


if __name__ == "__main__":
    main()
