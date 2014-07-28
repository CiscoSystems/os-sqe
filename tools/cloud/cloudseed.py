import os
import yaml
import crypt

from config import opts
from network import Network, Network6
from network import DOMAIN_NAME
from config import TEMPLATE_PATH, DIR_PATH
from tempfile import NamedTemporaryFile
from cloudtools import run_cmd, make_network_name

with open(os.path.join(TEMPLATE_PATH, "host_template.yaml")) as f:
    hostconf = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "vm.yaml")) as f:
    vmconf = yaml.load(f)


class SeedStorage:
    def __init__(self, lab_id, server, path, num, full_conf):
        self.lab_id = lab_id
        self.server = server
        self.index = num
        self.yaml = vmconf[self.server]["user-yaml"]
        self.path = path
        self.full_conf = full_conf
        self.cmd = []
        self.ydict = yaml.load(self.yaml)

    def define_credentials(self):
        self.ydict['users'][1]['ssh-authorized-keys'] = hostconf['id_rsa_pub']
        self.ydict['users'][1]['passwd'] = crypt.crypt(self.ydict['users'][1]['passwd'], "$6$rounds=4096")
        self.ydict['write_files'][0]['content'] = "\n".join(hostconf['id_rsa_pub'])

    def define_interfaces(self):
        nets = self.full_conf['networks']
        ifupdown = []
        for num, net in enumerate(nets):
            net_name = make_network_name(self.lab_id, net.keys()[0])
            network = Network.pool[net_name][1]
            combine_func = Network6.network_combine if network.ipv6 else Network.network_combine
            interface = network.interface
            if not network.dhcp:
                interface_ip = combine_func(
                    network.net_ip,
                    Network.hosts[0][self.server][self.index]['ip_base']
                )
                interface_text = interface.format(int_name="eth" + str(num), int_ip=interface_ip)
            else:
                interface_text = interface.format(int_name="eth" + str(num))
            if opts.distro == "ubuntu":
                interface_path = "/etc/network/interfaces.d/eth{int_num}.cfg"
            else:
                interface_path = "/etc/sysconfig/network-scripts/ifcfg-eth{int_num}"
            self.ydict["write_files"].append({
                "content": interface_text,
                "path": interface_path.format(int_num=num),
            })
            ifupdown.append("eth{int_num}".format(int_num=num))
        for cmd in self.ydict['runcmd']:
            if "ifdown" in cmd:
                for i in ifupdown:
                    self.cmd.append("/sbin/ifdown {int} && /sbin/ifup {int}".format(int=i))
                    self.cmd.append("service networking restart")

    def define_hosts(self):
        hostname = Network.hosts[0][self.server][self.index]['hostname']
        hosts_file = hostconf['hosts_template'].format(
            server_name=hostname,
            domain_name=DOMAIN_NAME)
        self.ydict["write_files"].append({"content": hosts_file, "path": "/etc/hosts"})
        for cmd in self.ydict['runcmd']:
            if "hostname" in cmd:
                self.cmd.append("/bin/hostname " + hostname)
                self.cmd.append("/bin/echo " + hostname + " > /etc/hostname")

    def define(self):
        self.define_credentials()
        self.define_interfaces()
        self.define_hosts()
        for cmd in self.ydict['runcmd']:
            if cmd not in ("hostname", "ifdown"):
                self.cmd.append(cmd)
        self.ydict['runcmd'] = self.cmd
        return yaml.dump(self.ydict)

    def create(self):
        c_localds = os.path.join(DIR_PATH, "cloud-localds")
        cloud_init = self.define()
        with NamedTemporaryFile() as temp:
            temp.write("#cloud-config\n" + cloud_init)
            temp.flush()
            run_cmd([c_localds, "-d", "qcow2", self.path, temp.name])
