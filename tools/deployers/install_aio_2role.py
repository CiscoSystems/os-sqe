#!/usr/bin/env python
from StringIO import StringIO
import urllib2
import argparse
import sys
import yaml
import os
import re

from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import sed, exists
from fabric.colors import green, red, yellow
from workarounds import fix_2role as fix

__author__ = 'sshnaidm'

CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../libvirt-scripts", "templates")


def quit_if_fail(command):
    if command.failed:
        print(red('FAB ERROR: Command failed'))
        if 'command' in command.__dict__:
            print(red('FAB ERROR: Command {cmd} returned {code}'.format(
                cmd=command.command, code=command.return_code)))
        sys.exit(command.return_code)


def warn_if_fail(command):
    if command.failed:
        print(yellow('FAB ERROR: Command failed'))
        if 'command' in command.__dict__:
            print(yellow('FAB ERROR: Command {cmd} returned {code}'.format(
                cmd=command.command, code=command.return_code)))


def prepare2role(config, common_file):
    ip_re = re.compile("\d+\.\d+\.\d+\.\d+")

    def change_ip_to(string, ip):
        return ip_re.sub(ip, string)


    print " >>>> FABRIC "
    print config
    print " >>>> FABRIC "
    print common_file

    conf = yaml.load(common_file)

    conf["controller_public_address"] = config['servers']['control-servers'][0]['ip']
    conf["controller_admin_address"] = config['servers']['control-servers'][0]['ip']
    conf["controller_internal_address"] = config['servers']['control-servers'][0]['ip']
    conf["coe::base::controller_hostname"] = "control-server00"
    conf["domain_name"] = "domain.name"
    conf["ntp_servers"] = ["ntp.esl.cisco.com"]
    conf["external_interface"] = "eth4"
    conf["nova::compute::vncserver_proxyclient_address"] = "%{ipaddress_eth0}"
    conf["build_node_name"] = "build-server"
    conf["controller_public_url"] = change_ip_to(
        conf["controller_public_url"],
        config['servers']['control-servers'][0]['ip'])
    conf["controller_admin_url"] = change_ip_to(
        conf["controller_admin_url"],
        config['servers']['control-servers'][0]['ip'])
    conf["controller_internal_url"] = change_ip_to(
        conf["controller_internal_url"],
        config['servers']['control-servers'][0]['ip'])
    conf["cobbler_node_ip"] = config['servers']['build-server']['ip']
    conf["node_subnet"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".0"
    conf["node_gateway"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".1"
    conf["swift_internal_address"] = config['servers']['control-servers'][0]['ip']
    conf["swift_public_address"] = config['servers']['control-servers'][0]['ip']
    conf["swift_admin_address"] = config['servers']['control-servers'][0]['ip']
    conf['mysql::server::override_options']['mysqld']['bind-address'] = config['servers']['control-servers'][0]['ip']
    conf['internal_ip'] = "%{ipaddress_eth0}"
    conf['public_interface'] = "eth0"
    conf['private_interface'] = "eth0"
    return yaml.dump(conf)


def role_mappings(config):

    roles = {}
    for c in config["servers"]["control-servers"]:
        roles.update({c["hostname"]: "controller"})
    for c in config["servers"]["compute-servers"]:
        roles.update({c["hostname"]: "compute"})
    roles.update({config["servers"]["build-server"]["hostname"]: "build"})
    return yaml.dump(roles)


def run_control(conf,
                settings_dict,
                envs=None,
                verbose=None,):
    envs = envs or {}
    envs.update({"build_server_ip": conf['servers']['build-server']["ip"]})
    envs.update({"vendor": "cisco"})
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run
    print >> sys.stderr, "FABRIC connecting to", settings_dict["host_string"],
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        with cd("/root/"):
            warn_if_fail(run_func("/etc/init.d/ntp stop; ntpdate ntp.esl.cisco.com; /etc/init.d/ntp start"))
            warn_if_fail(run_func("apt-get update"))
            warn_if_fail(run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                                  '-o Dpkg::Options::="--force-confdef" -o '
                                  'Dpkg::Options::="--force-confold" dist-upgrade'))
            warn_if_fail(run_func("apt-get install -y git"))
            warn_if_fail(run_func("git clone -b icehouse https://github.com/CiscoSystems/puppet_openstack_builder"))
            with cd("/root/puppet_openstack_builder"):
                    run_func('git checkout i.0')
            with cd("/root/puppet_openstack_builder/install-scripts"):
                warn_if_fail(run_func("./setup.sh"))
                warn_if_fail(run_func("puppet agent -td --server=build-server.domain.name --pluginsync"))
                fix("controls_after_setup")


def install_openstack(settings_dict,
                      envs=None,
                      verbose=None,
                      url_script=None,
                      prepare=False,
                      force=False,
                      config=None):
    """
    Install OS with COI

    :param settings_dict: settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    :param url_script: URl of Cisco installer script from Chris
    :param force: Use if you don't connect via interface you gonna bridge later
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
    with open(os.path.join(CONFIG_PATH, "buildserver_yaml")) as f:
                    build_yaml = f.read()
    roles_file = role_mappings(config)
    print roles_file
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        # TODO: check statuses of commands
        with cd("/root/"):
            warn_if_fail(run_func("apt-get update"))
            warn_if_fail(run_func("apt-get install -y git"))
            warn_if_fail(run_func("git config --global user.email 'test.node@example.com';"
                                  "git config --global user.name 'Test Node'"))
            warn_if_fail(put(StringIO(install_script), "/root/install_icehouse_cisco.sh", use_sudo=use_sudo_flag))
            if not force and not prepare:
                ## instead of Chris script
                warn_if_fail(run_func("/etc/init.d/ntp stop; ntpdate ntp.esl.cisco.com; /etc/init.d/ntp start"))
                warn_if_fail(run_func("apt-get update"))
                # # ## avoid grub and other prompts
                warn_if_fail(run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                                      '-o Dpkg::Options::="--force-confdef" -o '
                                      'Dpkg::Options::="--force-confold" dist-upgrade'))
                with cd("/root"):
                    warn_if_fail(run_func("git clone -b icehouse "
                                          "https://github.com/CiscoSystems/puppet_openstack_builder"))
                with cd("/root/puppet_openstack_builder"):
                    run_func('git checkout i.0')
                with cd("/root/puppet_openstack_builder/install-scripts"),  shell_env(**envs):
                    warn_if_fail(run_func("./install.sh"))
                warn_if_fail(get("/etc/puppet/data/hiera_data/user.common.yaml", "/tmp/user.common.yaml"))
                fd = StringIO()
                warn_if_fail(get("/etc/puppet/data/hiera_data/user.common.yaml", fd))
                new_user_common = prepare2role(config, fd.getvalue())
                print " >>>> FABRIC \n", new_user_common
                warn_if_fail(put(StringIO(new_user_common),
                                 "/etc/puppet/data/hiera_data/user.common.yaml",
                                 use_sudo=use_sudo_flag))
                warn_if_fail(put(StringIO(roles_file),
                                 "/etc/puppet/data/role_mappings.yaml",
                                 use_sudo=use_sudo_flag))
                #warn_if_fail(put(StringIO(build_yaml),
                #                 "/etc/puppet/data/hiera_data/hostname/build_server.yaml",
                #                 use_sudo=use_sudo_flag))
                run_func('puppet apply -v /etc/puppet/manifests/site.pp')
                if exists('/root/openrc'):
                    get('/root/openrc', "./openrc")
                else:
                    print (red("No openrc file, something went wrong! :("))
                print (green("Finished!"))
                return True
            elif not force and prepare:
                return True
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
    parser.add_argument('-b', action='store', default="", dest='build_server_ip',
                        help='Build-server IP for import')
    parser.add_argument('-l', action='store',
                        default=("https://gist.githubusercontent.com/rickerc/9836426/raw/"
                                 "93540685a1e611c52ac47af55d92f713b4af0a77/install_icehouse_cisco.sh"),
                        dest='url',
                        help='Url from where to download COI installer')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default='~/.ssh/id_rsa',
                        help='SSH key file, default=~/.ssh/id_rsa')
    parser.add_argument('-t', action='store_true', dest='test_mode', default=False,
                        help='Just run it to test host connectivity, if fine - return 0')
    parser.add_argument('-z', action='store_true', dest='prepare_mode', default=False,
                        help='Only prepare, don`t run the main script')
    parser.add_argument('-f', action='store_true', dest='force', default=False,
                        help='Force SSH client run. Use it if dont work')
    parser.add_argument('-w', action='store_true', dest='only_build', default=False,
                        help='Configure only build server')
    parser.add_argument('-c', action='store', dest='config_file', default=None,
                        help='Configuration file, default is None')
    parser.add_argument('--version', action='version', version='%(prog)s 1.0')

    opts = parser.parse_args()
    if opts.quiet:
        verb_mode = ['output', 'running', 'warnings']
    else:
        verb_mode = []
    if not opts.config_file:
        envs_build = {"default_interface": opts.default_interface,
                      "external_interface": opts.default_interface,
                      "vendor": "cisco",
                      "scenario": "2_role",
                      "build_server_ip": opts.build_server_ip}
        hosts = opts.hosts
        user = opts.user
        password = opts.password
        ssh_key_file = opts.ssh_key_file
        config = None
    else:
        with open(opts.config_file) as f:
            config = yaml.load(f)
        build = config['servers']['build-server']
        hosts = [build["ip"]]
        user = build["user"]
        password = build["password"]
        envs_build = {"default_interface": build["default_interface"],
                      "external_interface": build["external_interface"],
                      "vendor": "cisco",
                      "scenario": "2_role",
                      "build_server_ip": build["ip"]}
        ssh_key_file = opts.ssh_key_file

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
        sys.exit(run_probe(job_settings, verbose=verb_mode, envs=envs_build))
    for host in hosts:
        job_settings['host_string'] = host
        print job_settings
        print envs_build
        res = install_openstack(job_settings,
                                verbose=verb_mode,
                                envs=envs_build,
                                url_script=opts.url,
                                prepare=opts.prepare_mode,
                                force=opts.force,
                                config=config)
        if res:
            print "Job with host {host} finished successfully!".format(host=host)
    if not opts.only_build:
        for host in config["servers"]["control-servers"]:
            job_settings['host_string'] = host["ip"]
            run_control(config,
                        job_settings,
                        verbose=verb_mode,
                        envs=envs_build,
                        )
        for host in config["servers"]["compute-servers"]:
            job_settings['host_string'] = host["ip"]
            run_control(config,
                        job_settings,
                        verbose=verb_mode,
                        envs=envs_build,
                        )


if __name__ == "__main__":
    main()
