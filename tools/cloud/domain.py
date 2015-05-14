import os
import yaml

from network import Network
from storage import Storage
from cloudtools import conn, make_network_name
from config import TEMPLATE_PATH

with open(os.path.join(TEMPLATE_PATH, "network.yaml")) as f:
    netconf = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "vm.yaml")) as f:
    vmconf = yaml.load(f)
with open(os.path.join(TEMPLATE_PATH, "lab.yaml")) as f:
    env = yaml.load(f)


def construct_net_ip(lab_ip, net_shift):
    return ".".join(lab_ip.split(".")[:2] + [str(int(lab_ip.split(".")[-1]) + net_shift)] + ["0"])

class VM:
    pool = {}

    def __init__(self, lab_id, path, config, box):
        self.path = path
        self.lab_id = lab_id
        self.box = box
        self.conf = config["servers"][box]
        self.full_conf = config
        self.report = []
        self.names = [self.lab_id + "-" + self.box + "%.2d" % num if self.conf['params']['count'] != 1
                      else self.lab_id + "-" + self.box for num in xrange(self.conf['params']['count'])]
        ydict = yaml.load(vmconf[self.box]["user-yaml"])
        self.pool[box] = [
            {
                "vm_name": name,
                "user": ydict['users'][1]['name'],
                "password": ydict['users'][1]['passwd']
            } for name in self.names
        ]

    def network(self, index):
        xml = ""
        for key, net in enumerate(self.conf['params']['networks']):
            net_params = [i for i in self.full_conf['networks'] if net in i][0]
            box_net = Network.hosts[0][self.box][index]
            if "bridge" in net:
                a = netconf['template']["interface_bridge"]
                if net_params[net]:
                    xml += a.format(interface=net_params[net][0])
                    del net_params[net][0]
                continue
            if net_params[net]["dhcp"] or len(self.conf['params']['networks']) == 1:  # True or False
                mac = box_net["mac"]
                xml += netconf['template']["interface_dhcp"].format(
                    net_name=make_network_name(self.lab_id, net),
                    mac=mac
                )
                self.pool[self.box][index]["mac"] = mac
                self.pool[self.box][index]["ip"] = box_net["ip"]
                self.pool[self.box][index]["admin_interface"] = "eth" + str(key)
                self.pool[self.box][index]["eth" + str(key)] = box_net["ip"]
            else:
                xml += netconf['template']["interface"].format(net_name=make_network_name(self.lab_id, net))
            self.pool[self.box][index]["hostname"] = box_net["hostname"]
            if net_params[net]["external"]:
                self.pool[self.box][index]["external_interface"] = "eth" + str(key)
                if "external_net" not in self.pool:
                    if "ipv" in net_params[net] and net_params[net]["ipv"] == 6:
                        net_name = make_network_name(self.lab_id, net)
                        self.pool["external_net"] = Network.pool[net_name][1].net_ip
                    else:
                        self.pool["external_net"] = construct_net_ip(env[self.lab_id]["net_start"], key)
            if not net_params[net]["nat"]:
                self.pool[self.box][index]["internal_interface"] = "eth" + str(key)
        return xml

    def storage(self, index):
        return Storage.disks[self.names[index]]

    def define(self):
        return [vmconf[self.box]["xml"].format(
            name=self.names[num],
            ram=self.conf['params']["ram"]*1024*1024,
            cpu=self.conf['params']["cpu"],
            network=self.network(num),
            disk=self.storage(num),
        ) for num in xrange(self.conf['params']['count'])]

    def start(self):
        vm_xmls = self.define()
        for vm_xml in vm_xmls:
            vm = conn.defineXML(vm_xml)
            vm.create()
