import json
import random
import subprocess
import time
import unittest

from vts_tests.lib import cloud, vtcui, xrnc_node_connect, xrvr_node_connect, shell_connect
from vts_tests.lib import mercury_config as config
from vts_tests.tools import ports


class BaseTest(unittest.TestCase):

    XRVR_NO_SUCH_CONFIGURATION = 'No such configuration item(s)'

    @classmethod
    def setUpClass(cls):
        cls.config = config.Config()

    @property
    def cloud(self):
        if not hasattr(self, '_cloud'):
            self._cloud = cloud.Cloud('cloud',
                                      self.config.openrc['OS_USERNAME'],
                                      self.config.openrc['OS_PASSWORD'],
                                      self.config.openrc['OS_TENANT_NAME'],
                                      end_point=self.config.openrc['OS_AUTH_URL'])
        return self._cloud

    @property
    def vtc_ui(self):
        if not hasattr(self, '_vtc_ui'):
            self._vtc_ui = vtcui.VtcUI(self.config.vtc_ui_node['ui_ip'],
                                       self.config.vtc_ui_node['ui_user'],
                                       self.config.vtc_ui_node['ui_password'])
        return self._vtc_ui

    @property
    def vtc1(self):
        if not hasattr(self, '_vtc1'):
            self._vtc1 = shell_connect.ShellConnect(self.config.build_node, self.config.vtc_node1)
        return self._vtc1

    @property
    def vtc2(self):
        if not hasattr(self, '_vtc2') and self.config.vtc_node2:
            self._vtc1 = shell_connect.ShellConnect(self.config.build_node, self.config.vtc_node2)
        return getattr(self, '_vtc2')

    @property
    def xrnc1(self):
        if not hasattr(self, '_xrnc1'):
            self._xrnc1 = xrnc_node_connect.XrncNodeConnect(self.config.vtc_node1, self.config.xrnc_node1)
        return self._xrnc1

    @property
    def xrnc2(self):
        if not hasattr(self, '_xrnc2') and self.config.xrnc_node2:
            self._xrnc2 = xrnc_node_connect.XrncNodeConnect(self.config.vtc_node2, self.config.xrnc_node2)
        return getattr(self, '_xrnc2', None)

    @property
    def xrvr1(self):
        if not hasattr(self, '_xrvr1'):
            self._xrvr1 = xrvr_node_connect.XrvrNodeConnect(self.config.vtc_node1, self.config.xrvr_node1)
        return self._xrvr1

    @property
    def xrvr2(self):
        if not hasattr(self, '_xrvr2') and self.config.xrvr_node2:
            self._xrvr2 = xrnc_node_connect.XrvrNodeConnect(self.config.vtc_node2, self.config.xrvr_node2)
        return getattr(self, '_xrvr2', None)

    def convert_mac(self, mac_string):
        return '{0}{1}{2}{3}.{4}{5}{6}{7}.{8}{9}{10}{11}'.format(*mac_string.replace(':', '').lower())

    def create_net_subnet_port_instance(self):
        prefix = random.randint(1, 1000)

        # self.network = self.cloud.show_net(config.vts_config.get('default', 'network'))
        # self.subnet = self.cloud.show_subnet(self.network['subnets'])
        # self.networks = {self.network['name']: {'network': self.network, 'subnet': self.subnet}}

        # Uncomment to use new network/subnet every run
        self.networks = self.cloud.create_net_subnet(common_part_of_name=prefix, class_a=10, how_many=1, is_dhcp=False)

        self.ports = self.cloud.create_ports(instance_name=prefix, on_nets=self.networks, is_fixed_ip=True)
        self.instance, self.instance_status = self.cloud.create_instance(name=prefix,
                                                                         flavor=self.config.flavor,
                                                                         image=self.config.image_name,
                                                                         on_ports=self.ports)
        return self.instance, self.instance_status

    def create_access_ports(self):
        cfg = self.config.test_server_cfg
        if cfg:
            ports.create_ports(self.vtc_ui, cfg['tor_name'], cfg['tor_port'], cfg['ovs_bridge'], cfg['binding_host_id'])
            return True
        return False

    def delete_access_ports(self):
        cfg = self.config.test_server_cfg
        if cfg:
            ports.delete_ports(self.vtc_ui, cfg['tor_name'], cfg['tor_port'], cfg['ovs_bridge'])
            return True

    def get_port_ip(self, port):
        return json.loads(port['fixed_ips'].replace('\\', ''))['ip_address']

    def cmd(self, cmd):
        res = True
        output = ''
        try:
            output = subprocess.check_output(cmd, shell=True)
            print output
        except subprocess.CalledProcessError:
            res = False
        return res, output

    def instance_cmd(self, instance_ip, cmd):
        cmd = "sshpass -p {password} ssh -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null " \
              "{user}@{ip} \"{cmd}\"".format(user=self.config.image_user,
                                           password=self.config.image_password,
                                           ip=instance_ip, cmd=cmd)
        return self.cmd(cmd)

    def ping_ip(self, ip, attempts=24):
        res = False
        sleep_sec = 5
        for i in range(attempts):
            res, output = self.cmd('ping -W 120 -c 5 {ip}'.format(ip=ip))
            if res:
                break
            print "Ping failed. Sleep for {0} seconds".format(sleep_sec)
            time.sleep(5)
        return res

    def ping_ports(self, ports, attempts=12):
        res = []
        for p in ports:
            ip = self.get_port_ip(p)
            res.append(self.ping_ip(ip))
        return res

    def ping_remote_ports(self, source_ports, dest_ports):
        res = {}
        for sp in source_ports:
            for dp in dest_ports:
                sip = self.get_port_ip(sp)
                dip = self.get_port_ip(dp)
                cmd = "ping -W 120 -c 5 {ip}".format(user=self.config.image_user,
                                                     password=self.config.image_password,
                                                     ip=dip)
                res, output = self.instance_cmd(sip, cmd)
                res[(sip, dip)] = res
        return res

    def get_instance_ipv6_address(self, instance_ip, interface='eth0'):
        cmd = "/usr/sbin/ip address show {interface} | awk -F '[ /]' '/inet6/{{print \$6}}'".format(interface=interface)
        res, output = self.instance_cmd(instance_ip, cmd)
        return output.strip()
