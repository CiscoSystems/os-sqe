#!/usr/bin/env python
from StringIO import StringIO
import argparse
import sys
import yaml
import os
import time

from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, contains, sed
from fabric.colors import green, red

from utils import collect_logs, warn_if_fail, update_time, resolve_names, change_ip_to, dump
CONFIG_PATH=os.path.join(os.path.abspath(os.path.dirname(__file__)), "../libvirt-scripts", "templates")
__author__ = 'sshnaidm'


DOMAIN_NAME = "domain.name"
APPLY_LIMIT = 3
# override logs dirs if you need
#LOGS_COPY = {
#    "/etc": "etc_configs",
#    "/var/log": "all_logs",
#    "/etc/puppet": "puppet_configs",
#}

def prepare2role(config, common_file):
    """
        Function prepare user.common.yaml file according to lab configuration

    :param config: configuration of lab boxes
    :param common_file: the provided user.common.yaml from distro
    :return: text dump of new user.common.yaml file
    """

    print >> sys.stderr, " >>>> FABRIC box configurations"
    print config
    print >> sys.stderr, " >>>> FABRIC original user.common.yaml file"
    print common_file

    conf = yaml.load(common_file)
    print >> sys.stderr, " >>>> FABRIC loaded user.common.yaml file"
    print conf
    conf["controller_public_address"] = config['servers']['control-server'][0]['ip']
    conf["controller_admin_address"] = config['servers']['control-server'][0]['ip']
    conf["controller_internal_address"] = config['servers']['control-server'][0]['ip']
    conf["coe::base::controller_hostname"] = config['servers']['control-server'][0]['hostname']
    conf["domain_name"] = "domain.name"
    conf["ntp_servers"] = ["ntp.esl.cisco.com"]
    conf['public_interface'] = config['servers']['control-server'][0]['admin_interface']
    conf['private_interface'] = config['servers']['control-server'][0]['admin_interface']
    conf["external_interface"] = config['servers']['control-server'][0]['external_interface']
    conf['internal_ip'] = "%%{ipaddress_%s}" % config['servers']['control-server'][0]['admin_interface']
    conf["nova::compute::vncserver_proxyclient_address"] = "%%{ipaddress_%s}" % \
                                                           config['servers']['control-server'][0]['admin_interface']
    conf["build_node_name"] = config['servers']['build-server'][0]['hostname']
    conf["admin_user"] = "localadmin"
    conf["password_crypted"] = ("$6$UfgWxrIv$k4KfzAEMqMg.fppmSOTd0usI4j6gfjs0962."
                                "JXsoJRWa5wMz8yQk4SfInn4.WZ3L/MCt5u.62tHDGB36EhiKF1")
    conf["controller_public_url"] = change_ip_to(
        conf["controller_public_url"],
        config['servers']['control-server'][0]['ip'])
    conf["controller_admin_url"] = change_ip_to(
        conf["controller_admin_url"],
        config['servers']['control-server'][0]['ip'])
    conf["controller_internal_url"] = change_ip_to(
        conf["controller_internal_url"],
        config['servers']['control-server'][0]['ip'])
    conf["cobbler_node_ip"] = config['servers']['build-server'][0]['ip']
    conf["node_subnet"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".0"
    conf["node_gateway"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".1"
    conf["swift_internal_address"] = config['servers']['control-server'][0]['ip']
    conf["swift_public_address"] = config['servers']['control-server'][0]['ip']
    conf["swift_admin_address"] = config['servers']['control-server'][0]['ip']
    conf['mysql::server::override_options']['mysqld']['bind-address'] = config['servers']['control-server'][0]['ip']
    conf['ipv6_ra'] = 1
    conf['packages'] = conf['packages'] + " radvd"
    conf['install_drive'] = "/dev/vda"
    conf['service_plugins'] += ["neutron.services.metering.metering_plugin.MeteringPlugin"]
    return dump(conf)


def prepare_cobbler(config, cob_file):
    """
        Function creates cobbler configuration

    :param config:  configuration of lab boxes
    :param cob_file: the provided cobbler.yaml from distro
    :return: text dump of new cobbler.yaml file
    """
    new_conf = {}
    name = "trusty"
    with open(os.path.join(CONFIG_PATH, "cobbler.yaml")) as f:
        text_cobbler = f.read()
    text_cobbler = text_cobbler.format(
        int_ipadd="{$eth0_ip-address}",
        ip_gateway=".".join((config['servers']['build-server'][0]["ip"].split(".")[:3])) + ".1",
        ip_dns=".".join((config['servers']['build-server'][0]["ip"].split(".")[:3])) + ".1"
    )

    for c in config['servers']['control-server']:
        new_conf[c['hostname']] = {
            "hostname": c['hostname'] + "." + DOMAIN_NAME,
            "power_address": c["ip"],
            "profile": "%s-x86_64" % name,
            "interfaces": {
                "eth0": {
                    "mac-address": c["mac"],
                    "dns-name": c['hostname'] + "." + DOMAIN_NAME,
                    "ip-address": c["ip"],
                    "static": "0"
                }
            }
        }
    for c in config['servers']['compute-server']:
        new_conf[c['hostname']] = {
            "hostname": c['hostname'] + "." + DOMAIN_NAME,
            "power_address": c["ip"],
            "profile": "%s-x86_64" % name,
            "interfaces": {
                "eth0": {
                    "mac-address": c["mac"],
                    "dns-name": c['hostname'] + "." + DOMAIN_NAME,
                    "ip-address": c["ip"],
                    "static": "0"
                }
            }
        }

    return text_cobbler + "\n" + dump(new_conf)


def role_mappings(config):
    """
        Function creates role_mappings file

    :param config: configuration of lab boxes
    :return: text dump of new role_mappings.yaml file
    """
    roles = {}
    for c in config["servers"]["control-server"]:
        roles.update({c["hostname"]: "controller"})
    for c in config["servers"]["compute-server"]:
        roles.update({c["hostname"]: "compute"})
    roles.update({config["servers"]["build-server"][0]["hostname"]: "build"})
    return dump(roles)


def run_services(host,
                 settings_dict,
                 envs=None,
                 verbose=None,):
    """
        Install OS with COI on control and compute servers

    :param conf: configuration of lab boxes
    :param settings_dict: settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    """
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        run_func = sudo
        use_sudo_flag = True
    else:
        run_func = run
        use_sudo_flag = False
    print >> sys.stderr, "FABRIC connecting to", settings_dict["host_string"],
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        with cd("/root/"):
            update_time(run_func)
            run_func("apt-get update")
            run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                     '-o Dpkg::Options::="--force-confdef" -o '
                     'Dpkg::Options::="--force-confold" dist-upgrade')
            run_func("apt-get install -y git")
            run_func("git clone -b icehouse https://github.com/CiscoSystems/puppet_openstack_builder")
            ## run the latest, not i.0 release
            sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
                        "icehouse/snapshots/i.0",
                        "icehouse-proposed", use_sudo=use_sudo_flag)
            sed("/root/puppet_openstack_builder/data/hiera_data/vendor/cisco_coi_common.yaml",
                            "/snapshots/i.0",
                            "-proposed", use_sudo=use_sudo_flag)
            with cd("/root/puppet_openstack_builder/install-scripts"):
                warn_if_fail(run_func("./setup.sh"))
                warn_if_fail(run_func('puppet agent --enable'))
                warn_if_fail(run_func("puppet agent -td --server=build-server.domain.name --pluginsync"))
                collect_logs(run_func=run_func, hostname=host["hostname"])


def install_openstack(settings_dict,
                      envs=None,
                      verbose=None,
                      url_script=None,
                      prepare=False,
                      force=False,
                      config=None,
                      use_cobbler=False,
                      proxy=None):
    """
        Install OS with COI on build server

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
    with open(os.path.join(CONFIG_PATH, "buildserver_yaml")) as f:
                    build_yaml = f.read()
    roles_file = role_mappings(config)
    print "Job settings", settings_dict
    print "Env settings", envs
    print >> sys.stderr, roles_file
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        with cd("/root/"):
            if proxy:
                warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                                 "/etc/apt/apt.conf.d/00proxy",
                                 use_sudo=use_sudo_flag))
                warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                                 "/etc/apt/apt.conf.d/00no_pipelining",
                                 use_sudo=use_sudo_flag))
            run_func("apt-get update")
            run_func("apt-get install -y git")
            run_func("git config --global user.email 'test.node@example.com';"
                     "git config --global user.name 'Test Node'")
            if not force and not prepare:
                update_time(run_func)
                # avoid grub and other prompts
                warn_if_fail(run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                                      '-o Dpkg::Options::="--force-confdef" -o '
                                      'Dpkg::Options::="--force-confold" dist-upgrade'))
                warn_if_fail(run_func("git clone -b icehouse "
                                        "https://github.com/CiscoSystems/puppet_openstack_builder"))

                    ## run the latest, not i.0 release
                sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
                    "icehouse/snapshots/i.0",
                    "icehouse-proposed", use_sudo=use_sudo_flag)
                sed("/root/puppet_openstack_builder/data/hiera_data/vendor/cisco_coi_common.yaml",
                            "/snapshots/i.0",
                            "-proposed", use_sudo=use_sudo_flag)
                with cd("puppet_openstack_builder/install-scripts"):
                    warn_if_fail(run_func("./install.sh"))
                run_func("cp /etc/puppet/data/hiera_data/user.common.yaml /tmp/myfile")
                fd = StringIO()
                warn_if_fail(get("/etc/puppet/data/hiera_data/user.common.yaml", fd))
                new_user_common = prepare2role(config, fd.getvalue())
                print " >>>> FABRIC new user.common.file\n", new_user_common
                warn_if_fail(put(StringIO(new_user_common),
                                 "/etc/puppet/data/hiera_data/user.common.yaml",
                                 use_sudo=use_sudo_flag))
                warn_if_fail(put(StringIO(roles_file),
                                 "/etc/puppet/data/role_mappings.yaml",
                                 use_sudo=use_sudo_flag))
                fd = StringIO()
                warn_if_fail(get("/etc/puppet/data/cobbler/cobbler.yaml", fd))
                new_cobbler = prepare_cobbler(config, fd.getvalue())
                warn_if_fail(put(StringIO(new_cobbler),
                                 "/etc/puppet/data/cobbler/cobbler.yaml",
                                 use_sudo=use_sudo_flag))
                resolve_names(run_func, use_sudo_flag)
                result = run_func('puppet apply -v /etc/puppet/manifests/site.pp')
                tries = 1
                if use_cobbler:
                    cobbler_error = "[cobbler-sync]/returns: unable to connect to cobbler on localhost using cobbler"
                    while cobbler_error in result and tries <= APPLY_LIMIT:
                        time.sleep(60)
                        print >> sys.stderr, "Cobbler is not installed properly, running apply again"
                        result = run_func('puppet apply -v /etc/puppet/manifests/site.pp', pty=False)
                        tries += 1
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
                collect_logs(run_func=run_func, hostname=config["servers"]["build-server"][0]["hostname"], clean=True)
                print (green("Finished!"))
                return True
            elif not force and prepare:
                return True
    print (green("Finished!"))
    return True


def track_cobbler(config, setts):

    """
        Function for tracking cobbler installation on boxes

    :param config: boxes configuration
    :param setts: settings for connecting to boxes
    :return: Nothing, but exist with 1 when failed
    """

    def ping(h, s):
        with settings(**s), hide('output', 'running', 'warnings'):
            res = run("ping -W 5 -c 3 %s" % h)
            return res.succeeded

    def catalog_finished(h, s):
        s["host_string"] = h
        s["user"] = "localadmin"
        s["password"] = "ubuntu"
        with settings(**s), hide('output', 'running', 'warnings'):
            try:
                return contains("/var/log/syslog", "Finished catalog run")
            except Exception as e:
                return False

    wait_os_up = 20*60
    wait_catalog = 40*60
    hosts = config["servers"]["compute-server"] + config["servers"]["control-server"]
    # reset machines
    try:
        import libvirt
        conn = libvirt.open('qemu+ssh://{user}@localhost/system'.format(user=setts["user"]))
        for servbox in hosts:
            vm_name = servbox["vm_name"]
            vm = conn.lookupByName(vm_name)
            vm.destroy()
            vm.create()
            print >> sys.stderr, "Domain {name} is restarted...".format(name=vm_name)
        conn.close()
    except Exception as e:
        print >> sys.stderr, "Exception", e

    for check_func, timeout in (
            (ping, wait_os_up),
            (catalog_finished, wait_catalog)):

        host_ips = [i["ip"] for i in hosts]
        start = time.time()
        while time.time() - start < timeout:
            for host in host_ips:
                if check_func(host, setts.copy()):
                    host_ips.remove(host)
            if not host_ips:
                print >> sys.stderr, "Current step with '%s' was finished successfully!" % check_func.func_name
                break
            time.sleep(3*60)
        else:
            print >> sys.stderr, "TImeout of %d minutes of %s is over. Exiting...." % (timeout/60, check_func.func_name)
            sys.exit(1)


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
    parser.add_argument('-u', action='store', dest='user', default=None,
                        help='User to run the script with')
    parser.add_argument('-p', action='store', dest='password', default=None,
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
    parser.add_argument('-k', action='store', dest='ssh_key_file', default=None,
                        help='SSH key file, default is from repo')
    parser.add_argument('-t', action='store_true', dest='test_mode', default=False,
                        help='Just run it to test host connectivity, if fine - return 0')
    parser.add_argument('-e', action='store_true', dest='use_cobbler', default=False,
                        help='Use cobbler for deploying control and compute nodes')
    parser.add_argument('-z', action='store_true', dest='prepare_mode', default=False,
                        help='Only prepare, don`t run the main script')
    parser.add_argument('-f', action='store_true', dest='force', default=False,
                        help='Force SSH client run. Use it if dont work')
    parser.add_argument('-w', action='store_true', dest='only_build', default=False,
                        help='Configure only build server')
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
        envs_build = {"default_interface": opts.default_interface,
                      "external_interface": opts.default_interface,
                      "vendor": "cisco",
                      "scenario": "2_role",
                      "build_server_ip": opts.build_server_ip}
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
        build = config['servers']['build-server'][0]
        host = build["ip"]
        user = opts.user or build["user"]
        password = opts.password or build["password"]
        envs_build = {
            "vendor": "cisco",
            "scenario": "2_role",
            "build_server_ip": build["ip"]
        }

    job_settings = {"host_string": host,
                    "user": user,
                    "password": password,
                    "warn_only": True,
                    "key_filename": ssh_key_file,
                    "abort_on_prompts": True,
                    "gateway": opts.gateway}
    print >> sys.stderr, job_settings
    res = install_openstack(job_settings,
                            verbose=verb_mode,
                            envs=envs_build,
                            url_script=opts.url,
                            prepare=opts.prepare_mode,
                            force=opts.force,
                            config=config,
                            use_cobbler=opts.use_cobbler,
                            proxy=opts.proxy)
    if res:
        print "Job with host {host} finished successfully!".format(host=host)
    if not opts.only_build:
        if opts.use_cobbler:
            job_settings['host_string'] = host
            track_cobbler(config, job_settings)
        else:
            for host in config["servers"]["control-server"]:
                job_settings['host_string'] = host["ip"]
                run_services(host,
                             job_settings,
                             verbose=verb_mode,
                             envs=envs_build,
                             )
            for host in config["servers"]["compute-server"]:
                job_settings['host_string'] = host["ip"]
                run_services(host,
                             job_settings,
                             verbose=verb_mode,
                             envs=envs_build,
                             )

if __name__ == "__main__":
    main()
