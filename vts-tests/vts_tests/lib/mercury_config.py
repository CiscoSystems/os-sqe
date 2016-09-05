import functools
import io
import os
import re
import ConfigParser

from vts_tests.lib import shell_connect


class Config(object):

    CONTAINER_VTF_NAME = 'neutron-vtf'
    PROCESS_VPFA_NAME = 'vpfa_restconf_server'

    def __init__(self):
        self._vts_test_config_path = os.environ.get('VTS_TEST_CONFIG')
        if not self._vts_test_config_path:
            raise Exception('Environment variable VTS_TEST_CONFIG is not specified')
        if not os.path.exists(self._vts_test_config_path):
            raise Exception('Could not find VTS_TEST_CONFIG file: {0}'.format(self._vts_test_config_path))

        self._vts_test_config = None
        self._build_node = None
        self._vtc_node1 = None
        self._vtc_node2 = None
        self._vtc_ui_node = None
        self._xrnc_node1 = None
        self._xrnc_node2 = None
        self._xrvr_node1 = None
        self._xrvr_node2 = None
        self._mercury_servers_info = None
        self._controllers = None
        self._computes = None
        self._secrets = None
        self._openrc = None
        self._test_server_cfg = None

    @property
    def vts_test_config(self):
        if not self._vts_test_config:
            self._vts_test_config = ConfigParser.RawConfigParser(allow_no_value=True)
            self._vts_test_config.read([self._vts_test_config_path])
        return self._vts_test_config

    @property
    def default_node_user(self):
        return self.vts_test_config.get('default', 'node_user')

    @property
    def default_node_password(self):
        return self.vts_test_config.get('default', 'node_password')

    @property
    def image_user(self):
        return self.vts_test_config.get('default', 'image_user')

    @property
    def image_password(self):
        return self.vts_test_config.get('default', 'image_password')

    @property
    def image_name(self):
        return self.vts_test_config.get('default', 'image_name')

    @property
    def flavor(self):
        return self.vts_test_config.get('default', 'flavor')

    @property
    def build_node(self):
        if not self._build_node:
            self._build_node = {'ip': self.vts_test_config.get('build_node', 'ip'),
                                'hostname': self.vts_test_config.get('build_node', 'hostname'),
                                'user': self.default_node_user,
                                'password': self.default_node_password}
        return self._build_node

    @property
    def vtc_node1(self):
        if not self._vtc_node1:
            self._vtc_node1 = {'ip': self.vts_test_config.get('vtc1', 'ip'),
                               'user': self.vts_test_config.get('vtc1', 'user'),
                               'password': self.vts_test_config.get('vtc1', 'password'),
                               'hostname': self.vts_test_config.get('vtc1', 'hostname')}
        return self._vtc_node1

    @property
    def vtc_node2(self):
        if not self._vtc_node2 and self.vts_test_config.has_section('vtc2'):
            self._vtc_node2 = {'ip': self.vts_test_config.get('vtc2', 'ip'),
                               'user': self.vts_test_config.get('vtc2', 'user'),
                               'password': self.vts_test_config.get('vtc2', 'password'),
                               'hostname': self.vts_test_config.get('vtc2', 'hostname')}
        return self._vtc_node2

    @property
    def vtc_ui_node(self):
        if not self._vtc_ui_node:
            self._vtc_ui_node = {'ui_ip': self.vts_test_config.get('vtc', 'ui_ip'),
                                 'ui_user': self.vts_test_config.get('vtc', 'ui_user'),
                                 'ui_password': self.vts_test_config.get('vtc', 'ui_password')}
        return self._vtc_ui_node

    @property
    def xrnc_node1(self):
        if not self._xrnc_node1:
            self._xrnc_node1 = {'ip': self.vts_test_config.get('xrnc1', 'ip'),
                                'user': self.vts_test_config.get('xrnc1', 'user'),
                                'password': self.vts_test_config.get('xrnc1', 'password'),
                                'hostname': self.vts_test_config.get('xrnc1', 'hostname')}
        return self._xrnc_node1

    @property
    def xrnc_node2(self):
        if not self._xrnc_node2 and self.vts_test_config.has_section('xrnc2'):
            self._xrnc_node2 = {'ip': self.vts_test_config.get('xrnc2', 'ip'),
                                'user': self.vts_test_config.get('xrnc2', 'user'),
                                'password': self.vts_test_config.get('xrnc2', 'password'),
                                'hostname': self.vts_test_config.get('xrnc2', 'hostname')}
        return self._xrnc_node2

    @property
    def xrvr_node1(self):
        if not self._xrvr_node1:
            self._xrvr_node1 = {'ip': self.vts_test_config.get('xrvr1', 'ip'),
                                'user': self.vts_test_config.get('xrvr1', 'user'),
                                'password': self.vts_test_config.get('xrvr1', 'password'),
                                'hostname': self.vts_test_config.get('xrvr1', 'hostname')}
        return self._xrvr_node1

    @property
    def xrvr_node2(self):
        if not self._xrvr_node2 and self.vts_test_config.has_section('xrvr2'):
            self._xrvr_node2 = {'ip': self.vts_test_config.get('xrvr2', 'ip'),
                                'user': self.vts_test_config.get('xrvr2', 'user'),
                                'password': self.vts_test_config.get('xrvr2', 'password'),
                                'hostname': self.vts_test_config.get('xrvr2', 'hostname')}
        return self._xrvr_node2

    @property
    def mercury_servers_info(self):
        if not self._mercury_servers_info:
            b = shell_connect.ShellConnect(self.build_node)
            self._mercury_servers_info = b.run('cat ~/openstack-configs/mercury_servers_info')
        return self._mercury_servers_info

    def parse_nodes_info(self, msi_string):
        nodes = []
        for s in msi_string.split('\r\n')[4:]:
            items = s.split()
            if len(items) == 13:
                nodes.append({'hostname': items[1],
                              'cimc': items[3],
                              'management': items[5],
                              'ip': items[5],
                              'provision': items[7],
                              'tenant': items[9],
                              'user': self.default_node_user,
                              'password': self.default_node_password})
        return nodes

    @property
    def controllers(self):
        if not self._controllers:
            start_pos = self.mercury_servers_info.index('Controller nodes:')
            end_pos = self.mercury_servers_info.index('Compute nodes:')
            s = self.mercury_servers_info[start_pos:end_pos]
            self._controllers = self.parse_nodes_info(s)
        return self._controllers

    @property
    def computes(self):
        if not self._computes:
            start_pos = self.mercury_servers_info.index('Compute nodes:')
            end_pos = self.mercury_servers_info.index('VTS nodes:')
            s = self.mercury_servers_info[start_pos:end_pos]
            self._computes = self.parse_nodes_info(s)
        return self._computes

    @property
    def secrets(self):
        if not self._secrets:
            b = shell_connect.ShellConnect(self.build_node)
            secrets_info = b.run('cat ~/openstack-configs/secrets.yaml')
            self._secrets = ConfigParser.RawConfigParser(allow_no_value=True)
            self._secrets.readfp(io.BytesIO('[DEFAULT]\r\n' + secrets_info))
            self._secrets.get = functools.partial(self._secrets.get, 'DEFAULT')
        return self._secrets

    @property
    def openrc(self):
        if not self._openrc:
            self._openrc = {}
            b = shell_connect.ShellConnect(self.build_node)
            openrc_info = b.run('cat ~/openstack-configs/openrc && echo')
            for s in openrc_info.split('\r\n'):
                g = re.search(r'export (?P<name>\w+)=(?P<value>.*)', s)
                self._openrc[g.group('name')] = g.group('value')
        return self._openrc

    @property
    def test_server_cfg(self):
        if not self._test_server_cfg and self.vts_test_config.has_section('tests_server'):
            self._test_server_cfg = \
                {'tor_name': self.vts_test_config.get('tests_server', 'tor_name'),
                 'tor_port': self.vts_test_config.get('tests_server', 'tor_port'),
                 'ovs_bridge': self.vts_test_config.get('tests_server', 'ovs_bridge'),
                 'binding_host_id': self.vts_test_config.get('tests_server', 'binding_host_id')}
        return self._test_server_cfg
