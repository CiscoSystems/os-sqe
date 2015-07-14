# Copyright 2014 Cisco Systems, Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from fabric.api import local, settings, sudo, put, get, run, cd, lcd
from fabric.context_managers import shell_env
import yaml
import exceptions
import re
import os
import sys
from StringIO import StringIO


from fabs import lab
from fabs.common import logger as log

CONN = None


def _conn():
    import libvirt
    global CONN

    if not CONN:
        CONN = libvirt.open()
    return CONN


class CloudStatus:
    def __init__(self, lab_id):
        self.lab_id = lab_id
        self.info = {'controller': [], 'ucsm': [], 'network': [], 'compute': []}
        self.mac_2_ip = {}
        self.hostname_2_ip = {}

    def get(self, role, parameter):
        """
            :param role: controller, network, compute, ucsm
            :param parameter: ip, mac, hostname
            :return: a list of values for given parameter of given role
        """
        return [server.get(parameter) for server in self.info.get(role, [])]

    def get_first(self, role, parameter):
        """
            :param role: controller, network, compute, ucsm
            :param parameter: ip, mac, hostname
            :return: the first value for given parameter of given role
        """
        values = self.get(role=role, parameter=parameter)
        if values:
            return values[0]
        else:
            return 'NoValueFor' + role + parameter

    def set(self, role, ip, mac, hostname):
        """ Set all parameters for the given server"""
        self.hostname_2_ip[hostname] = ip
        self.mac_2_ip[mac] = ip
        if role in self.info.keys():
            self.info[role].append({'ip': ip, 'mac': mac, 'hostname': hostname})

    def create_open_rc(self):
        """ Creates open_rc for the given cloud"""
        open_rc = """
export OS_USERNAME=admin
export OS_TENANT_NAME=admin
export OS_PASSWORD=admin
export OS_AUTH_URL=http://{ip}:5000/v2.0/
export OS_REGION_NAME=RegionOne
"""
        with open('{id}.open_rc'.format(id=self.lab_id), 'w') as f:
            f.write(open_rc.format(ip=self.get_first('controller', 'ip')))

    def log(self):
        log.info('\n\n Report on lab: ' + str(self.lab_id))
        for hostname in sorted(self.hostname_2_ip.keys()):
            log.info(hostname + ': ' + self.hostname_2_ip[hostname])
        log.info('\n')
        for role in sorted(self.info.keys()):
            log.info(role + ' ip: ' + ' '.join(self.get(role=role, parameter='ip')))


class MyLab:
    LAB_IDX_MIN = 0
    LAB_IDX_MAX = 99

    def __init__(self, lab_id, topology_name, devstack_conf_addon='', is_only_xml=False):
        topo_path = os.path.join(lab.TOPOLOGIES_DIR, topology_name + '.yaml')
        with open(topo_path) as f:
            self.topology = yaml.load(f)
        self.is_only_xml = is_only_xml
        self.lab_id = int(lab_id)
        if self.lab_id < MyLab.LAB_IDX_MIN or self.lab_id > MyLab.LAB_IDX_MAX:
            msg = 'lab_id is supposed to be integer ' \
                  ' in the range [{min}-{max}], you gave {current}'\
                .format(current=lab_id, min=MyLab.LAB_IDX_MIN,
                        max=MyLab.LAB_IDX_MAX)
            sys.exit(msg)
        lab.make_tmp_dir(local_dir=lab.IMAGES_DIR)
        lab.make_tmp_dir(local_dir=lab.DISKS_DIR)
        lab.make_tmp_dir(local_dir=lab.XMLS_DIR)
        self.devstack_conf_addon = devstack_conf_addon  # string to be added at the end of all local.conf
        self.status = CloudStatus(lab_id=lab_id)

    def delete_of_something(self, list_of_something):
        import libvirt

        for something in list_of_something():
            if '{0}'.format(self.lab_id) in something.name():
                try:
                    something.destroy()
                except libvirt.libvirtError:
                    print >> sys.stderr, '{0} is not active, undefining...'.format(something.name())
                something.undefine()
                log.info('{0} was deleted'.format(something.name()))

    def delete_lab(self):
        self.delete_of_something(_conn().listAllDomains)
        self.delete_of_something(_conn().listAllNetworks)
        local('rm -f {0}/*{1}*'.format(lab.DISKS_DIR, self.lab_id))
        for bridge in local("brctl show | grep 8000 | grep {0} | awk '{{print $1}}'".format(self.lab_id), capture=True).split('\n'):
            if bridge:
                local('sudo ip l s {0} down && sudo brctl delbr {0}'.format(bridge))

    def create_networks(self):
        from bs4 import BeautifulSoup

        log.info('\n\nStarting IaaS phase- creating nets')
        list_of_networks = self.topology.get('networks', [])
        if not list_of_networks:
            log.info('Nothing defined in networks section')
            return

        for network_template in self.topology['networks']:
            if 'ipv6_prefix' in network_template:
                xml = network_template.format(lab_id=self.lab_id, ipv6_prefix=self.define_ipv6_prefix())
            else:
                xml = network_template.format(lab_id=self.lab_id)
            b = BeautifulSoup(xml, 'lxml')
            net_name = b.find('name').string
            self.save_xml(name='net-' + net_name, xml=xml)
            if not self.is_only_xml:
                net = _conn().networkDefineXML(xml)
                net.create()
                net.setAutostart(True)
                log.info('Network {} created'.format(net_name))

    def define_ipv6_prefix(self):
        try:
            prefix = re.search('2001.*::/', local('ip -6 r', capture=True)).group(0)
            return prefix.replace('/', str(1000+self.lab_id))
        except AttributeError:
            raise Exception('No globally routed v6 prefix found in routers table!')

    def create_domains(self):
        from bs4 import BeautifulSoup

        log.info('\n\nStarting IaaS phase- creating VMs')
        list_of_domains = self.topology.get('servers', [])
        if not list_of_domains:
            log.info('Nothing defined in servers section')
            return

        for domain_template in self.topology['servers']:
            b = BeautifulSoup(domain_template, 'lxml')

            hostname = b.find('name').string.format(lab_id=self.lab_id)
            host_type = hostname.split('-')[-1]
            # todo kshileev - what if we have two mac adresses
            # and only second one is for ip resolving is needed?
            mac = b.find('mac')['address'].format(lab_id=self.lab_id)
            image_url = b.find(string=re.compile('^http'))

            image_path = lab.wget_file(local_dir=lab.IMAGES_DIR, file_url=image_url)
            main_disk_path = self.create_main_disk(image_path=image_path, hostname=hostname, is_no_backing='disk_no_backing' in domain_template)

            if 'disk_cloud_init' in domain_template:
                cloud_init_disk_path = self.create_cloud_init_disk(hostname=hostname)
            else:
                cloud_init_disk_path = 'NoCloudInitDiskRequested'

            xml = domain_template.format(lab_id=self.lab_id,
                                         disk=main_disk_path,
                                         disk_no_backing=main_disk_path,
                                         disk_cloud_init=cloud_init_disk_path)
            self.save_xml(name=hostname, xml=xml)
            if not self.is_only_xml:
                domain = _conn().defineXML(xml)
                domain.create()
                net = b.find('interface').find('source')['network'].format(lab_id=self.lab_id)
                ip = lab.ip_for_mac_by_looking_at_libvirt_leases(net=net, mac=mac)
                self.status.set(role=host_type, ip=ip, mac=mac, hostname=hostname)
                log.info(msg='Domain {0} created'.format(hostname))

    @staticmethod
    def search_for(regexp, xml):
        return regexp.search(xml).group(1).strip()

    def save_xml(self, name, xml):
        with open(self.make_local_file_name(where=lab.XMLS_DIR, name=name, extension='xml'), 'w') as f:
            f.write(xml)

    def create_main_disk(self, image_path, hostname, is_no_backing):
        main_disk_path = self.make_local_file_name(where=lab.DISKS_DIR, name=hostname, extension='qcow2')
        if is_no_backing:
            local('cp {i} {d}'.format(i=image_path, d=main_disk_path))
        else:
            local('qemu-img create -f qcow2 -b {i} {d} 15G'.format(i=image_path, d=main_disk_path))
        return main_disk_path

    def create_cloud_init_disk(self, hostname):
        cloud_init_disk_path = self.make_local_file_name(where=lab.DISKS_DIR, name=hostname, extension='cloud_init.qcow2')
        user_data = self.make_local_file_name(where=lab.DISKS_DIR, name=hostname, extension='user_data')
        meta_data = self.make_local_file_name(where=lab.DISKS_DIR, name=hostname, extension='meta_data')
        local('echo "#cloud-config\npassword: ubuntu\nchpasswd: {{ expire: False }}\nssh_pwauth: True\n" > {0}'.format(user_data))
        local('echo instance_id: $(uuidgen) > {0}'.format(meta_data))
        local('echo local-hostname: {1} >> {0}'.format(meta_data, hostname))
        local('cloud-localds -d qcow2 {ci_d} {u_d} {m_d}'.format(ci_d=cloud_init_disk_path, u_d=user_data, m_d=meta_data))
        return cloud_init_disk_path

    @staticmethod
    def make_local_file_name(where, name, extension):
        return os.path.abspath(os.path.join(where, name + '.' + extension))

    def create_paas(self, phase):
        log.info('\n\nStarting {0} phase'.format(phase))
        paas_phase = self.topology.get(phase, [])
        if not paas_phase:
            log.info('Nothing defined in {0} section'.format(phase))
            return

        for segment in paas_phase:
            # possible values: net, mac, ip, hostname, user, password, cmd.
            host = {key: segment.get(key, 'Unknown_' + key).format(lab_id=self.lab_id) for key in ['hostname', 'net', 'mac', 'ip']}
            host['user'] = segment.get('user', 'ubuntu')
            host['password'] = segment.get('password', 'ubuntu')
            host['role'] = host['hostname'].split('-')[-1]
            commands = segment['cmd']

            if not host['hostname'].startswith('Unknown'):
                if host['ip'].startswith('Unknown'):
                    ip = self.status.hostname_2_ip[host['hostname']]
                else:
                    ip = host['ip']
            elif not host['mac'].startswith('Unknown'):
                ip = self.status.mac_2_ip[host['mac']]
            elif host['net'].startswith('local'):
                ip = '127.0.0.1'
            elif host['net'].startswith('2001:'):
                ip = lab.ip_for_mac_and_prefix(host['mac'], prefix=host['net'])
            else:
                raise exceptions.UserWarning('no way to determine where to execute! you provided hostname={hostname} net={net} mac={mac}')

            for cmd in commands:
                cmd = cmd.format(lab_id=self.lab_id)
                if ip in ['localhost', '127.0.0.1']:
                    local(cmd)
                else:
                    with settings(host_string='{user}@{ip}'.format(user=host['user'], ip=ip), password=host['password'], connection_attempts=50, warn_only=False):
                        if cmd.startswith('deploy_devstack'):
                            self.deploy_by_devstack(cmd)
                        elif cmd.startswith('deploy_by_packstack'):
                            self.deploy_by_packstack(cmd=cmd)
                        elif cmd.startswith('deploy_dibbler'):
                            self.deploy_dibbler(cmd)
                        elif cmd.startswith('put_config'):
                            self.put_config(cmd)
                        elif cmd.startswith('get_artifact'):
                            self.get_artifact(cmd)
                        elif cmd.startswith('run_tempest'):
                            self.run_tempest(cmd)
                        elif cmd.startswith('run_neutron_api_tests'):
                            self.run_neutron_api_tests()
                        elif cmd.startswith('register_as'):
                            self.status.set(role=host['role'], ip=host['ip'], mac=host['mac'], hostname=host['hostname'])
                        else:
                            sudo(cmd)

    def run_pre_or_post(self, pre_or_post):
        log.info('\n\nStarting {0} phase'.format(pre_or_post))
        list_of_commands = self.topology.get(pre_or_post, [])
        if not list_of_commands:
            log.info('Nothing defined in {0} section'.format(pre_or_post))
            return
        else:
            for cmd in list_of_commands:
                if cmd.startswith('run_tempest_local'):
                    self.run_tempest_local()
                else:
                    local(cmd.format(lab_id=self.lab_id))

    @staticmethod
    def clone_repo(repo_url):
        import urlparse

        local_repo_dir = urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        with settings(warn_only=True):
            # This is workaround for ubuntu update fails with
            # Hash Sum mismatch on some packages
            sudo('rm /var/lib/apt/lists/* -vrf')
            sudo('apt-get -y -q update && apt-get install -y -q git')
            if run('test -d {0}'.format(local_repo_dir)).failed:
                run('git clone -q {0}'.format(repo_url))
        with cd(local_repo_dir):
            run('git pull -q')
        return local_repo_dir

    def build_config_from_base_and_addon(self, directory, cmd):
        from fabs.ucsm import ucsm

        with open(os.path.join(directory, 'base.conf')) as f:
            conf_as_string = f.read()
        addon_config_name = cmd.split(' with ')[-1]
        with open(os.path.join(directory, addon_config_name)) as f:
            conf_as_string += f.read()
            conf_as_string += self.devstack_conf_addon
            conf_as_string = conf_as_string.replace('{controller_ip}', self.status.get_first(role='controller', parameter='ip'))
            conf_as_string = conf_as_string.replace('{controller_name}', self.status.get_first(role='controller', parameter='hostname'))
            conf_as_string = conf_as_string.replace('{nova_ips}', ','.join(self.status.get(role='compute', parameter='ip')))
            conf_as_string = conf_as_string.replace('{nova_ips}', ','.join(self.status.get(role='compute', parameter='ip')))
            conf_as_string = conf_as_string.replace('{neutron_ips}', ','.join(self.status.get(role='network', parameter='ip')))
            if 'ucsm' in addon_config_name:
                ucsm_user = 'ucspe'
                ucsm_password = 'ucspe'
                ucsm_service_profile = 'test-profile'
                ucsm_ip = self.status.get_first(role='ucsm', parameter='ip')
                ucsm(host=ucsm_ip, username=ucsm_user, password=ucsm_password, service_profile_name=ucsm_service_profile)
                conf_as_string = conf_as_string.replace('{ucsm_ip}', ucsm_ip)
                conf_as_string = conf_as_string.replace('{ucsm_username}', ucsm_user)
                conf_as_string = conf_as_string.replace('{ucsm_password}', ucsm_password)
                l_hostnames = self.status.get(role='compute', parameter='hostname') + self.status.get(role='controller', parameter='hostname')
                conf_as_string = conf_as_string.replace('{ucsm_host_list}', ','.join([hostname + ':' + ucsm_service_profile for hostname in l_hostnames]))
        log.info(msg='Config for OS deployer:\n' + conf_as_string)
        return conf_as_string

    def deploy_by_devstack(self, cmd):
        conf_as_string = self.build_config_from_base_and_addon(directory=lab.DEVSTACK_CONF_DIR, cmd=cmd)

        local_cloned_repo = MyLab.clone_repo('https://git.openstack.org/openstack-dev/devstack.git')
        put(local_path=StringIO(conf_as_string), remote_path='{0}/local.conf'.format(local_cloned_repo))
        run('{0}/stack.sh'.format(local_cloned_repo))

    def deploy_by_packstack(self, cmd):
        conf_as_string = self.build_config_from_base_and_addon(directory=lab.PACKSTACK_CONF_DIR, cmd=cmd)

        with settings(warn_only=True):
            if run('rpm -q openstack-packstack').failed:
                sudo('yum install -y -q http://rdo.fedorapeople.org/rdo-release.rpm')
                sudo('yum install -y -q openstack-packstack')
        put(local_path=StringIO(conf_as_string), remote_path='cisco-sqe-packstack.conf')
        sudo('packstack --answer-file=cisco-sqe-packstack.conf')
        self.create_tempest_conf(controller_ip=self.status.get(role='controller', parameter='ip'))

    @staticmethod
    def deploy_dibbler(cmd):
        dibbler_conf = cmd.split(' with ')[-1]
        local_cloned_repo = MyLab.clone_repo('https://github.com/tomaszmrugalski/dibbler.git')
        sudo('apt-get -yqq update && apt-get install -yqq git g++ make')
        with cd(local_cloned_repo):
            run('./configure')
            run('make --quiet')
            sudo('make install --quiet')
        sudo('mkdir -p /var/lib/dibbler')
        sudo('mkdir -p /var/log/dibbler')
        sudo('mkdir -p /etc/dibbler')
        put(local_path=lab.TOPOLOGIES_DIR + '/' + dibbler_conf, remote_path='/etc/dibbler/server.conf', use_sudo=True)
        sudo('dibbler-server start', pty=False)

    @staticmethod
    def put_config(cmd):
        """ Gets cmd in the form put_config local [remote]. Remote is optional, ~/local is used if not provided"""
        cmd_local_remote = cmd.split()
        config_local = cmd_local_remote[1]
        config_remote = cmd_local_remote[2] if len(cmd_local_remote) == 3 else config_local
        if 'etc' in config_remote:
            use_sudo = True
        else:
            use_sudo = False
        put(local_path=lab.TOPOLOGIES_DIR + '/' + config_local, remote_path=config_remote, use_sudo=use_sudo)

    @staticmethod
    def get_artifact(cmd):
        artifact_remote = cmd.split()[-1]
        artifact_local = os.path.basename(artifact_remote)
        get(remote_path=artifact_remote, local_path=artifact_local)

    @staticmethod
    def run_tempest(cmd):
        tempest_re = cmd.split(' ')[-1]
        tempest_dir = MyLab.get_path_for('tempest')
        with cd(tempest_dir):
            with settings(warn_only=True):
                run('testr init'.format(tempest_re))
                run('source .tox/venv/bin/activate && testr run {0}'.format(tempest_re))
                run('sudo pip install junitxml')
                run('testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=tempest_results.xml')
        get(remote_path=tempest_dir + '/tempest_results.xml', local_path='tempest_results.xml')

    @staticmethod
    def run_neutron_api_tests():
        tempest_dir = MyLab.get_path_for('tempest')
        neutron_dir = MyLab.get_path_for('neutron')
        with cd(neutron_dir):
            with shell_env(TEMPEST_CONFIG_DIR="{0}/etc/".format(tempest_dir)):
                run('tox -e api')
                run('sudo pip install junitxml')
                run('testr last --subunit | subunit-1to2 | subunit2junitxml '
                    '--output-to=neutron_api_results.xml')
        get(remote_path=neutron_dir + '/neutron_api_results.xml',
            local_path='neutron_api_results.xml')

    @staticmethod
    def get_path_for(component_name):
        """
        Reads remote devstack's local.conf to determine where stack.sh installed
        given component
        :param component_name: openstack component name
        :return:  path to installed openstack componentd
        """
        devstack_conf = StringIO()
        get(remote_path='devstack/local.conf', local_path=devstack_conf)
        match = re.search('DEST=(.+)\n', devstack_conf.getvalue())
        if match:
            path = match.groups()[0].strip() + '/{}'.format(component_name)
            if 'HOME' in path:
                path = run('echo {0}'.format(path))
        else:
            path = "/opt/stack/{}".format(component_name)
        return path

    @staticmethod
    def run_tempest_local():
        """Checkout tempest locally, configure tempest.conf and run versus OS declared via keystonerc_admin (RedHat packstack style)"""

        if local('test -d tempest').failed:
            local('git clone https://github.com/cisco-openstack/tempest.git && git checkout proposed')

        local('cp cisco-sqe-tempest.conf tempest/etc/tempest.conf')
        local('sudo pip install tox')
        with lcd('tempest'):
            local('tox -efull')
            with settings(warn_only=True):
                local('. .tox/full/bin/activate && pip install junitxml')
                local('. .tox/full/bin/activate && testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=cisco-sqe-tempest-results.xml')
            local('mv cisco-sqe-tempest-results.xml ..')

    @staticmethod
    def create_tempest_conf(controller_ip):
        from os_inspector import OS

        os_inspector = OS(ip=controller_ip)
        os_inspector.create_tempest_conf()

    def create_lab(self, phase):
        """Possible phases: lab, paas_pre, net, dom, paas_1, pass_2, paas_post, delete. lab does all in chain. delete cleans up the lab"""
        if phase not in ['paas_1', 'paas_2', 'paas_pre', 'paas_post']:
            self.delete_lab()
            if phase == 'delete':
                return

        if phase in ['lab', 'paas_pre']:
            self.run_pre_or_post(pre_or_post='paas_pre')
        if phase in ['lab', 'net', 'dom']:
            self.create_networks()
        if phase in ['lab', 'dom']:
            self.create_domains()
            self.status.log()
        if phase in ['lab', 'paas_1']:
            self.create_paas(phase='paas_1')
        if phase in ['lab', 'paas_2']:
            self.create_paas(phase='paas_2')
        if phase in ['lab', 'paas_post']:
            self.run_pre_or_post(pre_or_post='paas_post')
        self.status.log()
