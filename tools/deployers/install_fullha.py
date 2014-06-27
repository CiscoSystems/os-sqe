#!/usr/bin/env python
from StringIO import StringIO
import argparse
import sys
import yaml
import os
import re
import time

from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, contains, append, sed
from fabric.colors import green, red, yellow

__author__ = 'sshnaidm'

dump = lambda x: yaml.dump(x, default_flow_style=False)
CONFIG_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../libvirt-scripts", "templates")
DOMAIN_NAME = "domain.name"
ip_re = re.compile("\d+\.\d+\.\d+\.\d+")
APPLY_LIMIT = 3
LOGS_COPY = {
    "/etc": "etc_configs",
    "/var/log": "all_logs",
    "/etc/puppet": "puppet_configs",
}


def logs_bu(run_func=None, hostname=None, start=False):
    dirname = "test_data"
    if "WORKSPACE" in os.environ:
        path = os.path.join(os.environ["WORKSPACE"], dirname)
    else:
        cur_dir = os.path.dirname(__file__)
        path = os.path.join(cur_dir, dirname)
    if not os.path.exists(path):
        os.mkdir(path)
    if start:
        for i in os.listdir(path):
            os.remove(os.path.join(path, i))
    for dirlog in LOGS_COPY:
        filename = LOGS_COPY[dirlog] + "_" + hostname
        run_func("tar -zcf /tmp/{filename}.tar.gz {dirlog} 2>/dev/null".format(filename=filename, dirlog=dirlog))
        get("/tmp/{filename}.tar.gz".format(filename=filename), path)
        run_func("rm -rf /tmp/{filename}.tar.gz".format(filename=filename))


def change_ip_to(string, ip):
    return ip_re.sub(ip, string)


def all_servers(config):
    ssum = lambda x,y: x+y if isinstance(y, list) else x + [y]
    return reduce(ssum, config['servers'].values(), [])


def quit_if_fail(command):
    """
        Function quits all application if given command failed

    :param command: Command to execute
    """
    if command.failed:
        print(red('FAB ERROR: Command failed'))
        if 'command' in command.__dict__:
            print(red('FAB ERROR: Command {cmd} returned {code}'.format(
                cmd=command.command, code=command.return_code)))
        sys.exit(command.return_code)


def warn_if_fail(command):
    """
        Function prints warning to log if given command failed

    :param command: Command to execute
    """
    if command.failed:
        print(yellow('FAB ERROR: Command failed'))
        if 'command' in command.__dict__:
            print(yellow('FAB ERROR: Command {cmd} returned {code}'.format(
                cmd=command.command, code=command.return_code)))


def update_time(func):
    """
        Update time on remote machine

    :param func: function to execute the ntpdate with
    """
    ntp = False
    if exists("/etc/init.d/ntp"):
        ntp = True
        func("/etc/init.d/ntp stop")
    if func("ntpdate ntp.esl.cisco.com").failed:
        if func("ntpdate 10.81.254.202").failed:
            func("ntpdate ntp.ubuntu.com")
    if ntp:
        func("/etc/init.d/ntp start")


def prepare_files(config, paths, use_sudo_flag):

    def prepare_fullha(config, ha_file):
        conf = yaml.load(ha_file)
        net_ip = ".".join((config['servers']['control-servers'][0]['ip'].split(".")[:3]))
        vipc = net_ip + ".253"
        conf["coe::base::controller_hostname"] = "control-server"
        conf["horizon::keystone_url"] = change_ip_to(conf["horizon::keystone_url"], vipc)
        conf["controller_names"] = [c["hostname"] for c in config['servers']['control-servers']]
        conf["openstack-ha::load-balancer::controller_ipaddresses"] = [c["ip"]
                                                                       for c in config['servers']['control-servers']]
        conf["openstack-ha::load-balancer::swift_proxy_ipaddresses"] = [c["ip"]
                                                                       for c in config['servers']['swift-proxy']]
        conf["openstack-ha::load-balancer::swift_proxy_names"] = [c["hostname"]
                                                                       for c in config['servers']['swift-proxy']]
        vipsw = net_ip + ".252"
        conf["openstack::swift::proxy::swift_proxy_net_ip"] = vipsw
        conf["openstack::swift::proxy::swift_memcache_servers"] = [i["ip"] + ":11211"
                                                                   for i in config['servers']['swift-proxy']]
        conf["nova::memcached_servers"] = [i["ip"] + ":11211" for i in config['servers']['control-servers']]
        conf["rabbit_hosts"] = [i["hostname"] + ":5672" for i in config['servers']['control-servers']]
        conf["galera::galera_servers"] = [c["ip"] for c in config['servers']['control-servers']]
        conf["galera::galera_master"] = config['servers']['control-servers'][0]["hostname"] + "." + DOMAIN_NAME
        conf["galera_master_name"] = config['servers']['control-servers'][0]["hostname"]
        conf["galera_master_ipaddress"] = config['servers']['control-servers'][0]["ip"]
        conf["galera_backup_names"] = [i["hostname"] for i in config['servers']['control-servers'][1:]]
        conf["galera_backup_ipaddresses"] = [i["ip"] for i in config['servers']['control-servers'][1:]]
        conf["openstack::swift::storage-node::storage_devices"] += ["vdb", "vdc", "vdd"]
        return dump(conf)

    def prepare_common(config, common_file):
        conf = yaml.load(common_file)
        net_ip = ".".join((config['servers']['control-servers'][0]['ip'].split(".")[:3]))
        vipc = net_ip + ".253"
        conf["controller_public_address"] = vipc
        conf["controller_admin_address"] = vipc
        conf["controller_internal_address"] = vipc
        conf["coe::base::controller_hostname"] = "control-server"
        conf["domain_name"] = "domain.name"
        conf["ntp_servers"] = ["ntp.esl.cisco.com"]
        conf["external_interface"] = "eth4"
        conf["nova::compute::vncserver_proxyclient_address"] = "%{ipaddress_eth0}"
        conf["build_node_name"] = "build-server"
        conf["controller_public_url"] = change_ip_to(
            conf["controller_public_url"],
            vipc)
        conf["controller_admin_url"] = change_ip_to(
            conf["controller_admin_url"],
            vipc)
        conf["controller_internal_url"] = change_ip_to(
            conf["controller_internal_url"],
            vipc)
        conf["cobbler_node_ip"] = config['servers']['build-server']['ip']
        conf["node_subnet"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".0"
        conf["node_gateway"] = ".".join(conf["cobbler_node_ip"].split(".")[:3]) + ".1"
        vipsw = ".".join((config['servers']['control-servers'][0]['ip'].split(".")[:3])) + ".252"
        conf["swift_internal_address"] = vipsw
        conf["swift_public_address"] = vipsw
        conf["swift_admin_address"] = vipsw
        conf['mysql::server::override_options']['mysqld']['bind-address'] = "0.0.0.0"
        #    config['servers']['control-servers'][0]['ip']
        conf['swift_storage_interface'] = "eth2"
        conf['swift_local_net_ip'] = "%{ipaddress_eth2}"
        conf['internal_ip'] = "%{ipaddress_eth0}"
        conf['public_interface'] = "eth0"
        conf['private_interface'] = "eth0"
        conf['install_drive'] = "/dev/vda"
        conf['mon_initial_members'] = config['servers']['control-servers'][0]["hostname"]
        conf['ceph_primary_mon'] = config['servers']['control-servers'][0]["hostname"]
        conf['ceph_monitor_address'] = config['servers']['control-servers'][0]["ip"]
        conf['ceph_cluster_interface'] = "eth0"
        conf['ceph_cluster_network'] = net_ip + ".0/24"
        conf['ceph_public_interface'] = "eth0"
        conf['ceph_public_network'] = net_ip + ".0/24"
        return dump(conf)

    def prepare_cobbler(config, cob_file):
        new_conf = {}
        name = "trusty"
        with open(os.path.join(CONFIG_PATH, "cobbler.yaml")) as f:
            text_cobbler = f.read()
        text_cobbler = text_cobbler.format(
            int_ipadd="{$eth0_ip-address}",
            ip_gateway=".".join((config['servers']['build-server']["ip"].split(".")[:3])) + ".1",
            ip_dns=".".join((config['servers']['build-server']["ip"].split(".")[:3])) + ".1"
        )
        servers = config['servers']['control-servers'] + \
            config["servers"]["compute-servers"] + \
            config["servers"]["swift-storage"] + \
            config["servers"]["swift-proxy"] + \
            config["servers"]["load-balancer"]
        for c in servers:
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

        return text_cobbler + "\n" + yaml.dump(new_conf)

    def prepare_role(config, role_file):
        roles = {config["servers"]["build-server"]["hostname"]: "build"}
        for c in config["servers"]["control-servers"]:
            roles[c["hostname"]] = "controller"
        for c in config["servers"]["compute-servers"]:
            roles[c["hostname"]] = "compute"
        for c in config["servers"]["swift-storage"]:
            roles[c["hostname"]] = "swift_storage"
        for c in config["servers"]["swift-proxy"]:
            roles[c["hostname"]] = "swift_proxy"
        for c in config["servers"]["load-balancer"]:
            roles[c["hostname"]] = "load_balancer"
        return dump(roles)

    def prepare_build(config, build_file):
        return build_file

    for path in paths:
        fd = StringIO()
        warn_if_fail(get(path, fd))
        old_file = fd.getvalue()
        file_name = os.path.basename(path)
        print " >>>> FABRIC OLD %s\n" % file_name, old_file
        if file_name == "user.common.yaml":
            new_file = prepare_common(config, old_file)
        elif file_name == "user.full_ha.yaml":
            new_file = prepare_fullha(config, old_file)
        elif file_name == "cobbler.yaml":
            new_file = prepare_cobbler(config, old_file)
        elif file_name == "role_mappings.yaml":
            new_file = prepare_role(config, old_file)
        elif file_name == "build_server.yaml":
            new_file = prepare_build(config, old_file)
        print " >>>> FABRIC NEW %s\n" % file_name, new_file
        warn_if_fail(put(StringIO(new_file), path, use_sudo=use_sudo_flag))


def prepare_new_files(config, path, use_sudo_flag):
    for compute in config["servers"]["compute-servers"]:
        file_name = compute["hostname"] + ".yaml"
        new_path = os.path.join(path, file_name)
        ceph = {}
        ceph["cephdeploy::has_compute"] = True
        ceph["cephdeploy::osdwrapper::disks"] = ["vdb", "vdc", "vdd"]
        warn_if_fail(put(StringIO(dump(ceph)), new_path, use_sudo=use_sudo_flag))
        warn_if_fail(put(StringIO(dump(ceph)), os.path.join(path, file_name.replace("-", "_")),
                         use_sudo=use_sudo_flag))

def prepare_hosts(config):
    hosts = '\n'
    net_ip = ".".join(config["servers"]["control-servers"][0]["ip"].split(".")[:3])
    hosts += "{ip}    control.{domain}    control\n".format(ip=net_ip + ".253", domain=DOMAIN_NAME)
    hosts += "{ip}    swiftproxy.{domain}    swiftproxy\n".format(ip=net_ip + ".252", domain=DOMAIN_NAME)
    for s in all_servers(config):
        hosts += "{ip}    {hostname}.{domain}    {hostname}\n".format(
            ip=s["ip"],
            hostname=s["hostname"],
            domain=DOMAIN_NAME
        )
    return hosts


def run_services(host,
                 settings_dict,
                 envs=None,
                 verbose=None,
                 config=None):
    """
        Install OS with COI on control and compute servers

    :param host: configuration of current lab box
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
    print >> sys.stderr, "FABRIC connecting to", settings_dict["host_string"], host["hostname"]
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        with cd("/root/"):
            update_time(run_func)
            run_func("apt-get update")
            run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                     '-o Dpkg::Options::="--force-confdef" -o '
                     'Dpkg::Options::="--force-confold" dist-upgrade')
            # prepare /etc/hosts
            if config:
                append("/etc/hosts", prepare_hosts(config))
            run_func("apt-get install -y git")
            run_func("git clone -b icehouse https://github.com/CiscoSystems/puppet_openstack_builder")
            #with cd("/root/puppet_openstack_builder"):
            #        run_func('git checkout i.0')
            sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
                            "icehouse/snapshots/i.0",
                            "icehouse-proposed", use_sudo=use_sudo_flag)
            with cd("/root/puppet_openstack_builder/install-scripts"):
                warn_if_fail(run_func("./setup.sh"))
                warn_if_fail(run_func('puppet agent --enable'))
                warn_if_fail(run_func("puppet agent -td --server=build-server.domain.name --pluginsync"))
        logs_bu(run_func=run_func, hostname=host["hostname"])


def resolve_names(run_func, use_sudo_flag):
    import socket
    ip_arch = socket.gethostbyname("archive.ubuntu.com")
    ip_cisco = socket.gethostbyname("openstack-repo.cisco.com")
    run_func("echo -e '%s    archive.ubuntu.com\n' >> /etc/hosts" % ip_arch)
    run_func("echo -e '%s    openstack-repo.cisco.com\n' >> /etc/hosts" % ip_cisco)

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
                # prepare /etc/hosts file
                append("/etc/hosts", prepare_hosts(config))
                with cd("/root"):
                    warn_if_fail(run_func("git clone -b icehouse "
                                          "https://github.com/CiscoSystems/puppet_openstack_builder"))
                    with cd("puppet_openstack_builder"):
                        ## run the latest
                        #run_func('git checkout i.0')
                        sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
                            "icehouse/snapshots/i.0",
                            "icehouse-proposed", use_sudo=use_sudo_flag)
                        with cd("install-scripts"):
                            warn_if_fail(run_func("./install.sh"))
                prepare_files(config,
                              paths=(
                                  "/etc/puppet/data/hiera_data/user.common.yaml",
                                  "/etc/puppet/data/hiera_data/user.full_ha.yaml",
                                  "/etc/puppet/data/cobbler/cobbler.yaml",
                                  "/etc/puppet/data/role_mappings.yaml",
                                  "/etc/puppet/data/hiera_data/hostname/build_server.yaml"
                              ),
                              use_sudo_flag=use_sudo_flag)
                prepare_new_files(
                    config,
                    path="/etc/puppet/data/hiera_data/hostname",
                    use_sudo_flag=use_sudo_flag
                )
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
                logs_bu(run_func=run_func, hostname=config["servers"]["build-server"]["hostname"], start=True)
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

    wait_os_up = 15*60
    wait_catalog = 40*60
    hosts = config['servers']['control-servers'] + \
        config["servers"]["compute-servers"] + \
        config["servers"]["swift-storage"] + \
        config["servers"]["swift-proxy"] + \
        config["servers"]["load-balancer"]
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
    if not opts.config_file:
        envs_build = {
            "vendor": "cisco",
            "scenario": "full_ha",
            "build_server_ip": opts.build_server_ip
        }
        hosts = opts.hosts
        user = opts.user
        password = opts.password
        ssh_key_file = opts.ssh_key_file
        config = None
    else:
        try:
            with open(opts.config_file) as f:
                config = yaml.load(f)
        except IOError as e:
            print >> sys.stderr, "Not found file {file}: {exc}".format(file=opts.config_file, exc=e)
            sys.exit(1)
        build = config['servers']['build-server']
        hosts = [build["ip"]]
        user = build["user"]
        password = build["password"]
        envs_build = {
            "vendor": "cisco",
            "scenario": "full_ha",
            "build_server_ip": build["ip"]
        }
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
                                config=config,
                                use_cobbler=opts.use_cobbler,
                                proxy=opts.proxy)
        if res:
            print "Job with host {host} finished successfully!".format(host=host)
    if not opts.only_build:
        if opts.use_cobbler:
            job_settings['host_string'] = hosts[0]
            track_cobbler(config, job_settings)
        else:
            servers = config["servers"]["load-balancer"] + \
                config["servers"]["swift-storage"] + \
                config["servers"]["swift-proxy"] + \
                config["servers"]["control-servers"] + \
                config["servers"]["compute-servers"]
            for host in servers:
                job_settings['host_string'] = host["ip"]
                run_services(host,
                             job_settings,
                             verbose=verb_mode,
                             envs=envs_build,
                             config=config
                             )

if __name__ == "__main__":
    main()
