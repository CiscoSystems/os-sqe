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
from fabric.api import local, settings, sudo
import yaml
import exceptions
import re
import os
import libvirt
import sys


from fabs import lab
from fabs.common import logger as log


CONN = None


def _conn():
    global CONN

    if not CONN:
        CONN = libvirt.open()
    return CONN


class MyLab:
    def __init__(self, lab_id, topology_name, is_override, is_only_xml=False):
        topo_path = os.path.join(lab.TOPOLOGIES_DIR, topology_name + '.yaml')
        lab.make_tmp_dir(lab.DISKS_DIR)
        try:
            with open(topo_path) as f:
                self.topology = yaml.load(f)
            self.is_only_xml = is_only_xml
            self.lab_id = int(lab_id)
            self.image_url_re = re.compile(r'source +file.+(http.+) *-->')
            self.name_re = re.compile(r'<name>(.+)</name>')
            self.is_override = is_override
        except exceptions.ValueError:
            raise exceptions.Exception('lab_id is supposed to be integer')
        except:
            raise exceptions.Exception('wrong topology descriptor provided: {0}'.format(topo_path))

    def delete_of_something(self, list_of_something):
        for something in list_of_something():
            if 'lab-{0}'.format(self.lab_id) in something.name():
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

    def create_networks(self):
        log.info('\n\nStarting IaaS phase- creating nets')
        for network_template in self.topology['networks']:
            xml = network_template.format(lab_id=self.lab_id)
            if not self.is_only_xml:
                net = _conn().networkDefineXML(xml)
                net.create()
                net.setAutostart(True)
            self.save_xml(name=self.search_for(self.name_re, xml), xml=xml)

    def create_domains(self):
        log.info('\n\nStarting IaaS phase- creating VMs')
        for domain_template in self.topology['servers']:
            image_url = self.search_for(self.image_url_re, domain_template)
            domain_name = self.search_for(self.name_re, domain_template)

            image_local, kernel_local = self.wget_image(local_dir=lab.DISKS_DIR, image_url=image_url)
            disk_local, cloud_init_local = self.create_disk(image_local, domain_name)
            xml = domain_template.format(lab_id=self.lab_id, disk=disk_local, kernel=kernel_local, disk_cloud_init=cloud_init_local)
            if not self.is_only_xml:
                domain = _conn().defineXML(xml)
                domain.create()
            self.save_xml(name=domain_name, xml=xml)

    @staticmethod
    def search_for(regexp, xml):
        return regexp.search(xml).group(1).strip()

    def save_xml(self, name, xml):
        with open(self.make_local_file_name(where=lab.DISKS_DIR, name=name, extension='xml'), 'w') as f:
            f.write(xml)

    @staticmethod
    def wget_image(local_dir, image_url):
        image_local = os.path.abspath(os.path.join(local_dir, image_url.split('/')[-1]))
        kernel_local = None
        local('mkdir -p ' + local_dir)
        local('test -e  {local} || wget -nv {url} -O {local}'.format(url=image_url, local=image_local))
        if image_local.endswith('.tar.gz'):
            cmd = 'cd {image_dir} && tar xvf {image_local} --exclude=*-floppy --exclude=*-loader --exclude=README*'.format(image_dir=lab.IMAGES_DIR, image_local=image_local)
            ans = local(cmd, capture=True)
            for name in ans.split():
                if '.img' in name:
                    image_local = lab.IMAGES_DIR + '/' + name
                if 'vmlinuz' in name:
                    kernel_local = lab.IMAGES_DIR + '/' + name
        return image_local, kernel_local

    def create_disk(self, image_local, domain_name):
        disk_local = self.make_local_file_name(where=lab.DISKS_DIR, name=domain_name, extension='qcow2')
        local('qemu-img create -f qcow2 -b {i} {d}'.format(d=disk_local, i=image_local))
        disk_cloud_init = None
        if 'disk1' in image_local:
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
        log.info('\n\nStarting PAAS phase')
        for net_mac_cmd in self.topology['paas']:
            net = net_mac_cmd['net'].format(lab_id=self.lab_id)
            mac = net_mac_cmd['mac'].format(lab_id=self.lab_id)
            cmd = net_mac_cmd['cmd'].format(lab_id=self.lab_id)

            if net == 'local':
                local(cmd)
            else:
                ip = self.ip_for_mac(net=net, mac=mac)
                with settings(host_string='ubuntu@' + ip):
                    sudo(cmd)

    @staticmethod
    def ip_for_mac(net, mac):
        ans = local('sudo grep "{mac}" /var/lib/libvirt/dnsmasq/{net}.leases'.format(mac=mac, net=net), capture=True)
        return ans

    def create_lab(self):
        if self.is_override:
            self.delete_lab()
        self.create_networks()
        self.create_domains()
        self.create_paas()
