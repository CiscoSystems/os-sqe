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
import yaml
import exceptions
import re
import os
import libvirt
import sys
from StringIO import StringIO


from fabs import lab
from fabs.common import logger as log

CONN = None


def _conn():
    global CONN

    if not CONN:
        CONN = libvirt.open()
    return CONN


class MyLab:
    def __init__(self, lab_id, topology_name, devstack_conf_addon='', is_only_xml=False):
        topo_path = os.path.join(lab.TOPOLOGIES_DIR, topology_name + '.yaml')
        msg = None
        try:
            with open(topo_path) as f:
                self.topology = yaml.load(f)
            self.is_only_xml = is_only_xml
            self.lab_id = int(lab_id)
            if self.lab_id < 0 or self.lab_id > 99:
                raise ValueError()
            self.image_url_re = re.compile(r'source +file.+(http.+) *-->')
            self.name_re = re.compile(r'<name>(.+)</name>')
            lab.make_tmp_dir(local_dir=lab.IMAGES_DIR)
            lab.make_tmp_dir(local_dir=lab.DISKS_DIR)
            lab.make_tmp_dir(local_dir=lab.XMLS_DIR)
            self.control_ip = None  # will be filled in deploy_devstack if appropriate
            self.nova_ips = []
            self.neutron_ips = []
            self.devstack_conf_addon = devstack_conf_addon  # string to be added at the end of all local.conf
        except ValueError:
            msg = 'lab_id is supposed to be integer in the range [0-99], you gave {0}'.format(str(lab_id))
        except Exception as ex:
            msg = ex.message
        if msg:
            sys.exit(msg)

    def delete_of_something(self, list_of_something):
        for something in list_of_something():
            if 'lab-{0}-'.format(self.lab_id) in something.name():
                try:
                    something.destroy()
                except libvirt.libvirtError:
                    print >> sys.stderr, '{0} is not active, undefining...'.format(something.name())
                something.undefine()
                log.info('{0} was deleted'.format(something.name()))

    def delete_lab(self):
        self.delete_of_something(_conn().listAllDomains)
        self.delete_of_something(_conn().listAllNetworks)
        local('rm -f {0}/lab-{1}*'.format(lab.DISKS_DIR, self.lab_id))
        for bridge in local("brctl show | grep 8000 | grep {0} | awk '{{print $1}}'".format(self.lab_id), capture=True).split('\n'):
            if bridge:
                local('sudo ip l s {0} down && sudo brctl delbr {0}'.format(bridge))

    def create_networks(self):
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
            self.save_xml(name='net-'+self.search_for(self.name_re, xml), xml=xml)
            if not self.is_only_xml:
                net = _conn().networkDefineXML(xml)
                net.create()
                net.setAutostart(True)

    def define_ipv6_prefix(self):
        try:
            prefix = re.search('2001.*::/', local('ip -6 r', capture=True)).group(0)
            return prefix.replace('/', str(1000+self.lab_id))
        except AttributeError:
            raise Exception('No globally routed v6 prefix found in routers table!')

    def create_domains(self):
        log.info('\n\nStarting IaaS phase- creating VMs')
        list_of_domains = self.topology.get('servers', [])
        if not list_of_domains:
            log.info('Nothing defined in servers section')
            return

        for domain_template in self.topology['servers']:
            image_url = self.search_for(self.image_url_re, domain_template)
            domain_name = self.search_for(self.name_re, domain_template)

            image_local, kernel_local = self.wget_image(image_url=image_url)
            disk_local, cloud_init_local = self.create_disk(image_local=image_local, domain_name=domain_name,
                                                            is_use_cloud_init_disk='{disk_cloud_init}' in domain_template)
            xml = domain_template.format(lab_id=self.lab_id, disk=disk_local, kernel=kernel_local, disk_cloud_init=cloud_init_local)
            self.save_xml(name=domain_name, xml=xml)
            if not self.is_only_xml:
                domain = _conn().defineXML(xml)
                domain.create()

    @staticmethod
    def search_for(regexp, xml):
        return regexp.search(xml).group(1).strip()

    def save_xml(self, name, xml):
        with open(self.make_local_file_name(where=lab.XMLS_DIR, name=name, extension='xml'), 'w') as f:
            f.write(xml)

    @staticmethod
    def wget_image(image_url):
        image_local = lab.wget_file(local_dir=lab.IMAGES_DIR, file_url=image_url)
        kernel_local = None
        if image_local.endswith('.tar.gz'):
            cmd = 'cd {image_dir} && tar xvf {image_local} --exclude=*-floppy --exclude=*-loader --exclude=README*'.format(image_dir=lab.IMAGES_DIR,
                                                                                                                           image_local=image_local)
            ans = local(cmd, capture=True)
            for name in ans.split():
                if '.img' in name:
                    image_local = lab.IMAGES_DIR + '/' + name
                if 'vmlinuz' in name:
                    kernel_local = lab.IMAGES_DIR + '/' + name
        return image_local, kernel_local

    def create_disk(self, image_local, domain_name, is_use_cloud_init_disk):
        disk_local = self.make_local_file_name(where=lab.DISKS_DIR, name=domain_name, extension='qcow2')
        local('qemu-img create -f qcow2 -b {i} {d} 15G'.format(d=disk_local, i=image_local))
        disk_cloud_init = None
        if is_use_cloud_init_disk:
            disk_cloud_init = self.make_local_file_name(where=lab.DISKS_DIR, name=domain_name, extension='cloud_init.raw')
            user_data = self.make_local_file_name(where=lab.DISKS_DIR, name=domain_name, extension='user_data')
            meta_data = self.make_local_file_name(where=lab.DISKS_DIR, name=domain_name, extension='meta_data')
            local('echo "#cloud-config\npassword: ubuntu\nchpasswd: {{ expire: False }}\nssh_pwauth: True\n" > {0}'.format(user_data))
            local('echo instance_id: $(uuidgen) > {0}'.format(meta_data))
            local('cloud-localds {disk} {u_d} {m_d}'.format(disk=disk_cloud_init, u_d=user_data, m_d=meta_data))
        return disk_local, disk_cloud_init

    def make_local_file_name(self, where, name, extension):
        return os.path.abspath(os.path.join(where, name.format(lab_id=self.lab_id) + '.' + extension))

    def create_paas(self):
        log.info('\n\nStarting PaaS phase')
        if not self.topology.get('paas', []):
            log.info('Nothing defined in PaaS section')
            return
        for net_mac_user_password_cmds in self.topology['paas']:
            net = net_mac_user_password_cmds['net'].format(lab_id=self.lab_id)
            mac = net_mac_user_password_cmds['mac'].format(lab_id=self.lab_id)
            user = net_mac_user_password_cmds.get('user', 'ubuntu')
            password = net_mac_user_password_cmds.get('password', 'ubuntu')
            commands = net_mac_user_password_cmds['cmd']

            if net == 'local':
                ip = 'local'
            elif net.startswith('2001:'):
                ip = lab.ip_for_mac_and_prefix(mac=mac, prefix=net)
            elif net == 'baremetal':
                ip = mac
            else:
                ip = lab.ip_for_mac_by_looking_at_libvirt_leases(net=net, mac=mac)
                if not ip:
                    raise exceptions.UserWarning('failed to obtain IP from libvirt lease file')

            for cmd in commands:
                cmd = cmd.format(lab_id=self.lab_id)
                if ip == 'local':
                    local(cmd)
                else:
                    with settings(host_string='{user}@{ip}'.format(user=user, ip=ip), password=password, connection_attempts=50, warn_only=False):
                        if cmd.startswith('deploy_devstack'):
                            self.deploy_devstack(cmd, ip)
                        elif cmd.startswith('deploy_by_packstack'):
                            self.deploy_by_packstack(cmd=cmd, ip=ip)
                        elif cmd.startswith('deploy_dibbler'):
                            self.deploy_dibbler(cmd)
                        elif cmd.startswith('put_config'):
                            self.put_config(cmd)
                        elif cmd.startswith('get_artifact'):
                            self.get_artifact(cmd)
                        elif cmd.startswith('run_tempest'):
                            self.run_tempest(cmd)
                        elif cmd.startswith('register_as_control_node'):
                            self.control_ip = ip
                        elif cmd.startswith('register_as_nova_node'):
                            self.nova_ips.append(ip)
                        elif cmd.startswith('register_as_neutron_node'):
                            self.neutron_ips.append(ip)
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
        # This is workaround for ubuntu update fails with
        # Hash Sum mismatch on some packages
        sudo('rm /var/lib/apt/lists/* -vrf')

        sudo('apt-get -yqq update && apt-get install -yqq git')

        with settings(warn_only=True):
            sudo('apt-get -y -q update && apt-get install -y -q git')
            if run('test -d {0}'.format(local_repo_dir)).failed:
                run('git clone -q {0}'.format(repo_url))
        with cd(local_repo_dir):
            run('git pull -q')
        return local_repo_dir

    def deploy_devstack(self, cmd, ip):
        conf_local_path = os.path.join(lab.TOPOLOGIES_DIR, cmd.split(' with ')[-1])
        if not self.control_ip:
            self.control_ip = ip

        with open(conf_local_path) as f:
            conf_as_string = f.read()
            conf_as_string.replace('{control_ip}', str(self.control_ip))
            conf_as_string += self.devstack_conf_addon

        local_cloned_repo = MyLab.clone_repo('https://git.openstack.org/openstack-dev/devstack.git')
        put(local_path=StringIO(conf_as_string), remote_path='{0}/local.conf'.format(local_cloned_repo))
        run('{0}/stack.sh'.format(local_cloned_repo))

    def deploy_by_packstack(self, cmd, ip):
        conf_local_path = os.path.join(lab.TOPOLOGIES_DIR, cmd.split(' with ')[-1])
        if not self.control_ip:
            self.control_ip = ip

        with open(conf_local_path) as f:
            conf_as_string = f.read()
            conf_as_string = conf_as_string.replace('{controller_ip}', str(self.control_ip))
            conf_as_string = conf_as_string.replace('{nova_ips}', ','.join(self.nova_ips or [self.control_ip]))
            conf_as_string = conf_as_string.replace('{neutron_ips}', ','.join(self.neutron_ips or [self.control_ip]))

        with settings(warn_only=True):
            if run('rpm -q openstack-packstack').failed:
                sudo('yum install -y -q http://rdo.fedorapeople.org/rdo-release.rpm')
                sudo('yum install -y -q openstack-packstack')
        put(local_path=StringIO(conf_as_string), remote_path='cisco-sqe-packstack.conf')
        sudo('packstack --answer-file=cisco-sqe-packstack.conf')
        self.create_tempest_conf(controller_ip=self.control_ip)

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
        devstack_conf = StringIO()
        get(remote_path='devstack/local.conf', local_path=devstack_conf)
        match = re.search('DEST=(.+)\n', devstack_conf.getvalue())
        if match:
            tempest_dir = match.groups()[0].strip() + '/tempest'
        else:
            tempest_dir = '/opt/stack/tempest'
        with cd(tempest_dir):
            with settings(warn_only=True):
                run('testr init'.format(tempest_re))
                run('source .tox/venv/bin/activate && testr run {0}'.format(tempest_re))
                run('sudo pip install junitxml')
                run('testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=tempest_results.xml')
        get(remote_path=tempest_dir + '/tempest_results.xml', local_path='tempest_results.xml')

    @staticmethod
    def run_tempest_local():
        """Checkout tempest locally, configure tempest.conf and run versus OS declared via keystonerc_admin (RedHat packstack style)"""

        if local('test -d tempest').failed:
            local('git clone https://github.com/cisco-openstack/tempest.git && git checkout proposed')

        local('cp cisco-sqe-tempest.conf tempest/etc/tempest.conf')
        local('sudo pip install tox')
        with lcd('tempest'):
            local('tox -efull')
            local('source .tox/full/bin/activate && pip install junitxml')
            local('source .tox/full/bin/activate && testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=cisco-sqe-tempest-results.xml')
            local('mv cisco-sqe-tempest-results.xml ..')

    @staticmethod
    def create_tempest_conf(controller_ip):
        from os_inspector import OS

        os_inspector = OS(ip=controller_ip)
        os_inspector.create_tempest_conf()

    def create_lab(self, phase):
        """Possible phases: lab, paas_pre, net, dom, paas, delete. lab does all in chain. delete cleans up the lab"""
        if phase not in ['paas', 'paas_pre', 'paas_post']:
            self.delete_lab()
            if phase == 'delete':
                return

        if phase in ['lab', 'paas_pre']:
            self.run_pre_or_post(pre_or_post='paas_pre')
        if phase in ['lab', 'net', 'dom']:
            self.create_networks()
        if phase in ['lab', 'dom']:
            self.create_domains()
        if phase in ['lab', 'paas']:
            self.create_paas()
        if phase in ['lab', 'paas_post']:
            self.run_pre_or_post(pre_or_post='paas_post')
