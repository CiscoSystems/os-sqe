import argparse
import yaml
import sys

from fabric.api import sudo, settings, run, hide, local, put, shell_env, cd, get
from fabric.contrib.files import sed, exists, contains, append
from fabric.colors import green, red, yellow

__author__ = 'sshnaidm'


def apply_multi(config, user, password, gateway, force, verb_mode, ssh_key_file):

    def run_on_control(box, setts, verbose, run_func, use_sudo_flag):
        setts["host_string"] = box["ip"]
        print >> sys.stderr, "Configuring control machine", setts
        with settings(**setts), hide(*verbose):
            append("/etc/nova/nova.conf", "default_floating_pool=public", use_sudo=use_sudo_flag)
            run_func("service nova-api restart")

    def run_on_compute(box, setts, verbose, run_func, use_sudo_flag):
        setts["host_string"] = box["ip"]
        print >> sys.stderr, "Configuring compute machine", setts
        with settings(**setts), hide(*verbose):
            sed("/etc/nova/nova-compute.conf", "virt_type=kvm", "virt_type=qemu", use_sudo=use_sudo_flag)
            run_func("service nova-compute restart")


    job_settings = {"host_string": "",
                    "user": user,
                    "password": password,
                    "warn_only": True,
                    "key_filename": ssh_key_file,
                    "abort_on_prompts": True,
                    "gateway": gateway}
    if user != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run

    for control in config["servers"]["control-servers"]:
        run_on_control(control, job_settings, verb_mode, run_func, use_sudo_flag)
    for compute in config["servers"]["compute-servers"]:
        run_on_compute(compute, job_settings, verb_mode, run_func, use_sudo_flag)


def apply_aio(host, user, password, gateway, force, verb_mode, ssh_key_file):
    job_settings = {"host_string": host,
                    "user": user,
                    "password": password,
                    "warn_only": True,
                    "key_filename": ssh_key_file,
                    "abort_on_prompts": True,
                    "gateway": gateway}
    if user != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run
    if force:
        cmd = """sed -i 's/virt_type=kvm/virt_type=qemu/g' /etc/nova/nova-compute.conf; \
        service nova-compute restart; \
        sed -i 's/allow_versions = false/allow_versions = true/g' /etc/swift/container-server.conf; \
        swift-init container-server restart; \
        sed -i '2idefault_floating_pool=public' /etc/nova/nova.conf; \
        service nova-api restart;"""
        local('ssh {user}@{host} "{cmd}"'.format(user=user, host=host, cmd=cmd))

    else:
        with settings(**job_settings), hide(*verb_mode):
            append("/etc/nova/nova.conf", "default_floating_pool=public", use_sudo=use_sudo_flag)
            run_func("service nova-api restart")
            sed("/etc/nova/nova-compute.conf", "virt_type=kvm", "virt_type=qemu", use_sudo=use_sudo_flag)
            run_func("service nova-compute restart")
            sed("/etc/swift/container-server.conf", "allow_versions = false", "allow_versions = true",
                use_sudo=use_sudo_flag)
            run_func("swift-init container-server restart")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', action='store', dest='user',
                        help='User to run the script with')
    parser.add_argument('-p', action='store', dest='password',
                        help='Password for user and sudo')
    parser.add_argument('-a', action='store', dest='host', default='',
                        help='IP of host in case of AIO')
    parser.add_argument('-g', action='store', dest='gateway', default=None,
                        help='Gateway to connect to host')
    parser.add_argument('-q', action='store_true', default=False, dest='quiet',
                        help='Make all silently')
    parser.add_argument('-k', action='store', dest='ssh_key_file', default='~/.ssh/id_rsa',
                        help='SSH key file, default=~/.ssh/id_rsa')
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
    if not opts.config_file and not opts.host:
        print >> sys.stderr, "No config file and no IP to connect to!"
        sys.exit(1)
    elif opts.host:
        apply_aio(
            host=opts.host,
            user=opts.user,
            password=opts.password,
            gateway=opts.gateway,
            force=opts.force,
            verb_mode=verb_mode,
            ssh_key_file=opts.ssh_key_file
        )
    else:
        try:
            with open(opts.config_file) as f:
                config = yaml.load(f)
        except IOError as e:
            print >> sys.stderr, "Not found file {file}: {exc}".format(file=opts.config_file, exc=e)
            sys.exit(1)
        if "aio" in config["servers"]:
            apply_aio(
                host=config["servers"]["aio"]["ip"],
                user=opts.user,
                password=opts.password,
                gateway=opts.gateway,
                force=opts.force,
                verb_mode=verb_mode,
                ssh_key_file=opts.ssh_key_file
            )
        else:
            apply_multi(
                config,
                user=opts.user,
                password=opts.password,
                gateway=opts.gateway,
                force=opts.force,
                verb_mode=verb_mode,
                ssh_key_file=opts.ssh_key_file
            )

if __name__ == "__main__":
    main()
