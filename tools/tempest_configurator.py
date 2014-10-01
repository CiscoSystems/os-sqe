#!/usr/bin/env python
import argparse
import glob
import keystoneclient.v2_0.client
import novaclient.client
import neutronclient.v2_0.client
import glanceclient
import requests
import re
import os
import sys
import urllib
import urlparse
import ConfigParser

__author__ = 'sshnaidm'

env_re = re.compile("export (OS_[A-Z0-9_]+=.*$)")
token_re = re.compile("name='csrfmiddlewaretoken' value='([^']+)'")
ip_re = re.compile("((?:\d+\.){3}\d+)")
region_re = re.compile('name="region" type="hidden" value="([^"]+)"')
action_re = re.compile('action="([^"]+)"')

NOVACLIENT_VERSION = '2'
CINDERCLIENT_VERSION = '1'

DEFAULT_USER = "admin"
DEFAULT_PASS = "Cisco123"
DEFAULT_REGION = "RegionOne"
DEMO_USER = "demo"
DEMO_PASS = "secret"
DEMO_TENANT = "demo"
ALT_USER = "alt_demo"
ALT_PASS = "secret"
ALT_TENANT = "alt_demo"
DEFAULT_IPV4_INT = "192.168.1"
DEFAULT_IPV6_INT = "fd00::"


CIRROS_UEC_URL = "http://download.cirros-cloud.net/0.3.2/cirros-0.3.3-x86_64-uec.tar.gz"

IMAGES = {'image_ref': {'user': 'cirros',
                        'url': 'http://172.29.173.233/cirros-0.3.3-x86_64-disk.img',
                        'password': 'cubswin:)'},
          'image_ref_alt': {'user': 'ubuntu',
                            'url': 'http://172.29.173.233/trusty-server-cloudimg-amd64-disk1.img',
                            'password': 'ssh-key-only'},
          'alt_image_key': 'image_ref'}

class OS:

    def _get_identity_client(self, credentials):
            return keystoneclient.v2_0.client.Client(
                username=credentials["OS_USERNAME"],
                password=credentials["OS_PASSWORD"],
                tenant_name=credentials["OS_TENANT_NAME"],
                auth_url=credentials["OS_AUTH_URL"])

    def _get_network_client(self, credentials):
            return neutronclient.v2_0.client.Client(
                username=credentials["OS_USERNAME"],
                password=credentials["OS_PASSWORD"],
                tenant_name=credentials["OS_TENANT_NAME"],
                auth_url=credentials["OS_AUTH_URL"])

    def _get_image_client(self, credentials):
            keystone_cl = self._get_identity_client(credentials)
            token = keystone_cl.auth_token
            endpoint = keystone_cl.service_catalog.url_for(service_type="image")
            return glanceclient.Client('1', endpoint=endpoint, token=token)

    def _get_compute_client(self, credentials):
            client_args = (credentials["OS_USERNAME"], credentials["OS_PASSWORD"],
                           credentials["OS_TENANT_NAME"], credentials["OS_AUTH_URL"])
            return novaclient.client.Client(NOVACLIENT_VERSION,
                                            *client_args,
                                            region_name=credentials["OS_REGION_NAME"],
                                            no_cache=True,
                                            http_log_debug=True)

class OSWebCreds:
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password

    def get_file_from_url(self):
        local_params = {
            "username": self.user,
            "password": self.password,
        }
        s = requests.Session()
        add_urls = ["/horizon", "", "/dashboard"]
        for add_url in add_urls:
            url = "http://" + self.ip
            login_page = s.get(url + add_url)
            if (login_page.status_code == requests.codes.ok
                and "csrfmiddlewaretoken" in login_page.content):
                real_url = login_page.url
                break
        else:
            raise NameError("Can not download login page!")
        print "Getting credentials from Horizon: %s" % real_url
        token = token_re.search(login_page.content).group(1)
        region = region_re.search(login_page.content).group(1)
        local_params.update({"csrfmiddlewaretoken": token})
        local_params.update({"region": region})
        login_action = action_re.search(login_page.content).group(1)
        login_url = "http://" + self.ip + login_action
        s.post(login_url, data=local_params)
        rc_url = real_url + "/project/access_and_security/api_access/openrc/"
        rc_file = s.get(rc_url)
        return rc_file

    def parse_rc(self, x):
        export_lines = (i for i in x.split("\n") if env_re.search(i) and not "PASSWORD" in i)
        os_vars = (env_re.search(i).group(1) for i in export_lines)
        os_dict = dict(((z.replace("'", "").replace('"', '') for z in  i.split("=")) for i in os_vars))
        return os_dict

    def creds(self):
        rc_file = self.get_file_from_url()
        rc_dict = self.parse_rc(rc_file.content)
        if rc_dict:
            return dict(rc_dict, OS_PASSWORD=self.password, OS_REGION_NAME=DEFAULT_REGION)
        else:
            return None


class Tempest:
    def __init__(self, openrc):
        self.creds = openrc
        openstack = OS()
        self.nova = openstack._get_compute_client(self.creds)
        self.neutron = openstack._get_network_client(self.creds)
        self.keystone = openstack._get_identity_client(self.creds)
        self.glance = openstack._get_image_client(self.creds)
        self.ipv = openrc["ipv"]
        self.external_net = openrc["external_net"]
        self.tmp_dir = "/tmp/"
        self.curdir = os.path.dirname(__file__)
        self.locks_dir = os.path.abspath(os.path.join(self.curdir, "locks"))

    def unconfig(self):
        img_dir = os.path.join(self.curdir, "prepare_for_tempest_dir")
        if os.path.exists(img_dir):
            for i in os.listdir(img_dir):
                os.remove(os.path.join(img_dir,i))
        print "Deleting cirros-0.3.1-x86_64-disk.img ...."
        for i in glob.glob("./cirros-*img"):
            os.remove(i)
        #os.remove(os.path.join(cur_dir, "trusty-server-cloudimg-amd64-disk1.img"))
        print "Deleting glance images ....."
        for img in self.glance.images.list():
            self.glance.images.delete(img)
        print "Deleting demo tenants ....."
        for t in self.keystone.tenants.list():
            if t.name == DEMO_TENANT or t.name == ALT_TENANT:
                self.keystone.tenants.delete(t)
        print "Deleting demo users ....."
        for u in self.keystone.users.list():
            if u.name == DEMO_USER or u.name == ALT_USER:
                self.keystone.users.delete(u)
        print "Deleting floating ips ....."
        for i in self.neutron.list_floatingips()['floatingips']:
            self.neutron.delete_floatingip(i['id'])
        print "Clearing gateway from routers ...."
        for i in self.neutron.list_routers()['routers']:
            self.neutron.remove_gateway_router(i['id'])
        print "Deleting router ports ...."
        for i in [port for port in self.neutron.list_ports()['ports']]:
            if i['device_owner'] == 'network:router_interface':
                self.neutron.remove_interface_router(i['device_id'], {"port_id": i['id']})
            else:
                self.neutron.delete_port(i['id'])
        print "Deleting routers ...."
        for i in self.neutron.list_routers()['routers']:
            self.neutron.delete_router(i['id'])
        for i in self.neutron.list_networks()['networks']:

            self.neutron.delete_network(i['id'])
        for i in self.neutron.list_subnets()['subnets']:
            self.neutron.delete_subnet(i['id'])
        #for i in os.listdir(self.tmp_dir):
        #    if "cirros-0.3.1-x86_64-uec" in i:
        #        os.remove(i)

    def create_config(self):
        img_dir = os.path.join(self.curdir, "prepare_for_tempest_dir")
        print "Reinitialize the dir..."
        if os.path.exists(img_dir):
            for i in os.listdir(img_dir):
                os.remove(os.path.join(img_dir,i))
        else:
            os.makedirs(img_dir)
        if not os.path.exists(self.locks_dir):
            os.makedirs(self.locks_dir)

        def register_image(image_key):
            url = IMAGES[image_key]['url']
            img_path = os.path.join(img_dir + urlparse.urlparse(url).path)
            print 'Downloading {0} to {1}....'.format(url, img_path)
            urllib.urlretrieve(url, img_path)
            img = self.glance.images.create(
                data=open(img_path, 'rb'),
                name=IMAGES[image_key]['user'],
                disk_format="qcow2",
                container_format="bare",
                is_public=True)
            return img.id

        image_ref_id = register_image('image_ref')
        image_ref_alt_id = register_image(IMAGES['alt_image_key'])

        demo_tenant = self.keystone.tenants.create(DEMO_TENANT)
        demo_user = self.keystone.users.create(
            name=DEMO_USER,
            password=DEMO_PASS,
            email=DEMO_USER+"@spam.com",
            tenant_id=demo_tenant.id)
        alt_tenant = self.keystone.tenants.create(ALT_TENANT)
        alt_user = self.keystone.users.create(
            name=ALT_USER,
            password=ALT_PASS,
            email=ALT_USER+"@spam.com",
            tenant_id=alt_tenant.id)
        tenant_ids = dict((i.name, i.id) for i in self.keystone.tenants.list())
        if "openstack" in tenant_ids:
            admin_tenant = ("openstack", tenant_ids["openstack"])
        elif "admin" in tenant_ids:
            admin_tenant = ("admin", tenant_ids["admin"])
        else:
            _admin_tenant = self.keystone.tenants.create("admin")
            admin_tenant = ("admin", _admin_tenant.id)
        try:
            self.keystone.users.create(
                name=DEFAULT_USER,
                password=DEFAULT_PASS,
                email=DEFAULT_USER+"@spam.com",
                tenant_id=admin_tenant[1])
        except Exception as e:
            print e
        admin = next((i for i in self.keystone.users.list() if i.name == "admin"), None)
        # if not successful creating admin - set its password
        #admin = self.keystone.users.update_password(admin.id, DEFAULT_PASS)
        admin_role = next((i for i in self.keystone.roles.list() if i.name == "admin"), None)
        if admin is None or admin_role is None:
            print "Can not get admin details!"
            sys.exit(1)
        try:
            self.keystone.roles.add_user_role(
                user=admin.id,
                role=admin_role.id,
                tenant=admin_tenant[1])
        except Exception as e:
            print e
        self.keystone.roles.add_user_role(
            user=admin.id,
            role=admin_role.id,
            tenant=demo_tenant.id)
        public_net = self.neutron.create_network({
            'network':
                {'name': "public",
                 'admin_state_up': True,
                 "router:external": True
                }})
        if self.ipv == 4:
            sub_public = self.neutron.create_subnet({
                'subnet':
                    {'name':"public_subnet",
                     'network_id': public_net['network']['id'],
                     'ip_version': 4,
                     'cidr': self.external_net + '.0/24',
                     'allocation_pools': [{'start': self.external_net + '.50',
                                           'end': self.external_net + '.250'}],
                     'enable_dhcp': False,
                     'dns_nameservers': [self.external_net + ".1", '8.8.8.8']
                    }})
        else:
            sub_public = self.neutron.create_subnet({
                'subnet':
                    {'name':"public_subnet",
                     'network_id': public_net['network']['id'],
                     'ip_version': 6,
                     'cidr': self.external_net + '/64',
                     'allocation_pools': [{'start': self.external_net + ':30',
                                           'end': self.external_net + ':ffff'}],
                     'enable_dhcp': False,
                     'dns_nameservers': [self.external_net + "1"]
                    }})
        private_net = self.neutron.create_network({
            'network':
                {'name': "private",
                 'admin_state_up': True,
                 "shared": True,
                 "tenant_id": demo_tenant.id,
                }})
        if self.ipv == 4:
            sub_private = self.neutron.create_subnet({
                'subnet':
                    {'name':"private_subnet",
                     'network_id': private_net['network']['id'],
                     'ip_version': 4,
                     'cidr': DEFAULT_IPV4_INT + '.0/24',
                     'dns_nameservers': [self.external_net + ".1", '8.8.8.8']
                    }})
        else:
            sub_private = self.neutron.create_subnet({
                'subnet':
                    {'name':"private_subnet",
                     'network_id': private_net['network']['id'],
                     'ip_version': 6,
                     'cidr': DEFAULT_IPV6_INT + '/64',
                     'dns_nameservers': [self.external_net + "1"]
                    }})
        router = self.neutron.create_router({"router": {"name": "router1",
                                                        "tenant_id": demo_tenant.id}})
        self.neutron.add_interface_router(
            router['router']['id'],
            {"subnet_id": sub_private['subnet']['id']})
        self.neutron.add_gateway_router(
            router['router']['id'],
            {"network_id": public_net['network']['id']})
        if not os.path.exists(self.tmp_dir + "cirros-0.3.2-x86_64-uec.tar.gz"):
            urllib.urlretrieve(CIRROS_UEC_URL, self.tmp_dir + "cirros-0.3.2-x86_64-uec.tar.gz")

        return {
            'image_ref_id': image_ref_id,
            'image_ref_alt_id': image_ref_alt_id,
            "admin_tenant": admin_tenant,
            "admin": admin,
            "ip": ip_re.search(self.creds["OS_AUTH_URL"]).group(1),
            "admin_role": admin_role,
            "router": router,
            "public_net": public_net,
        }

    def create_config_file(self, data):


        if 'WORKSPACE' in os.environ:
            tempest_dir = os.path.abspath(os.path.join(os.environ['WORKSPACE'], "tempest/.venv/bin"))
        else:
            tempest_dir = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "..","tempest/.venv/bin"))
        if not os.path.exists(tempest_dir):
            tempest_dir = os.path.join(os.path.expanduser("~"), ".venv", "bin")
        tempest_dir = os.path.normpath(tempest_dir)
        parser = ConfigParser.SafeConfigParser(defaults={
            "debug": "True",
            "log_file": "tempest.log",
            "use_stderr": "False",
            "lock_path": self.locks_dir
        })
        parser.add_section("cli")
        parser.set('cli', "cli_dir", tempest_dir)
        parser.set('cli', 'enabled', 'True')
        parser.set('cli', 'has_manage', 'False')
        parser.add_section("compute")
        parser.set("compute", "catalog_type", "compute")
        #parser.set("compute", "ssh_connect_method", "floating")

        main_image_dict = IMAGES['image_ref']
        parser.set("compute", "image_ref", data['image_ref_id'])
        parser.set("compute", "flavor_ref", '1')
        parser.set("compute", "image_ssh_user", main_image_dict['user'])
        parser.set("compute", "image_ssh_password", main_image_dict['password'])

        alt_image_dict = IMAGES[IMAGES['alt_image_key']]
        parser.set("compute", "image_ref_alt", data['image_ref_alt_id'])
        parser.set("compute", "flavor_ref_alt", '2')
        parser.set("compute", "image_alt_ssh_user", alt_image_dict['user'])
        parser.set("compute", "image_alt_ssh_password", alt_image_dict['password'])

        parser.set("compute", "ssh_user", main_image_dict['user'])
        parser.set("compute", "run_ssh", "False")
        parser.set("compute", "ssh_timeout", "90")
        parser.set("compute", "use_floatingip_for_ssh", "True")
        parser.set("compute", "ssh_timeout", "196")
        parser.set("compute", "ip_version_for_ssh", str(self.ipv))

        #parser.set("compute", "network_for_ssh", "private")
        parser.set("compute", "fixed_network_name", "private")
        parser.set("compute", "allow_tenant_isolation", "False")
        parser.set("compute", "build_timeout", "300")
        parser.set("compute", "build_interval", "10")
        #parser.set("compute", "run_ssh", "True")
        #parser.set("compute", "ssh_connect_method", "fixed")
        parser.set("compute", "volume_device_name", "vdb")
        parser.add_section("compute-admin")
        parser.set("compute-admin", "tenant_name", data["admin_tenant"][0])
        parser.set("compute-admin", "password", DEFAULT_PASS)
        parser.set("compute-admin", "username", data["admin"].username)
        parser.add_section("compute-feature-enabled")
        parser.set("compute-feature-enabled", "block_migration_for_live_migration", "False")
        parser.set("compute-feature-enabled", "change_password", "False")
        parser.set("compute-feature-enabled", "live_migration", "False")
        parser.set("compute-feature-enabled", "resize", "False")
        parser.set("compute-feature-enabled", "api_v3", "False")
        parser.add_section("dashboard")
        parser.set("dashboard", "login_url", "http://%s/horizon/auth/login/" % data["ip"])
        parser.set("dashboard", "dashboard_url", "http://%s/horizon" % data["ip"])
        parser.add_section("identity")
        parser.set("identity", "disable_ssl_certificate_validation", "False")
        parser.set("identity", "catalog_type", "identity")
        parser.set("identity", "auth_version", "v2")
        parser.set("identity", "admin_domain_name", "Default")
        parser.set("identity", "admin_tenant_id", data["admin_tenant"][1])
        parser.set("identity", "admin_tenant_name", data["admin_tenant"][0])
        parser.set("identity", "admin_password", DEFAULT_PASS)
        parser.set("identity", "admin_username", data["admin"].username)
        parser.set("identity", "admin_role", data["admin_role"].name)
        parser.set("identity", "alt_tenant_name", ALT_TENANT)
        parser.set("identity", "alt_password", ALT_PASS)
        parser.set("identity", "alt_username", ALT_USER)
        parser.set("identity", "tenant_name", DEMO_TENANT)
        parser.set("identity", "password", DEMO_PASS)
        parser.set("identity", "username", DEMO_USER)
        parser.set("identity", "uri_v3", re.sub("/v2.0", "/v3", self.creds["OS_AUTH_URL"]))
        parser.set("identity", "uri", self.creds["OS_AUTH_URL"])
        parser.set("identity", "region", DEFAULT_REGION)
        parser.add_section("image")
        parser.set("image", "catalog_type", "image")
        parser.set("image", "api_version", "1")
        parser.set("image", "http_image", "http://172.29.173.233/cirros-0.3.2-x86_64-uec.tar.gz")
        parser.add_section("network")
        parser.set("network", "tenant_network_cidr", "172.16.0.0/12")
        parser.set("network", "tenant_network_v6_cidr", '2003::/48')
        parser.set("network", "tenant_network_mask_bits", "24")
        parser.set("network", "tenant_network_v6_mask_bits", "64")
        parser.set("network", "tenant_networks_reachable", "False")
        parser.set("network", "public_router_id", data['router']['router']['id'])
        parser.set("network", "public_network_id", data['public_net']['network']['id'])
        parser.add_section("network-feature-enabled")
        parser.set("network-feature-enabled", "api_extensions", "all")
        parser.set("network-feature-enabled", "ipv6_subnet_attributes", "True")
        parser.set("network-feature-enabled", "ipv6", "True")
        parser.add_section("scenario")
        parser.set("scenario", "large_ops_number", "0")
        parser.set("scenario", "aki_img_file", "cirros-0.3.2-x86_64-vmlinuz")
        parser.set("scenario", "ari_img_file", "cirros-0.3.2-x86_64-initrd")
        parser.set("scenario", "ami_img_file", "cirros-0.3.2-x86_64-blank.img")
        parser.set("scenario", "img_dir", "/tmp/cirros-0.3.2-x86_64-uec")
        parser.add_section("service_available")
        parser.set("service_available", "neutron", "True")
        parser.set("service_available", "heat", "True")
        parser.set("service_available", "ceilometer", "True")
        parser.set("service_available", "swift", "True")
        parser.set("service_available", "cinder", "False")
        parser.set("service_available", "nova", "True")
        parser.set("service_available", "glance", "True")
        parser.set("service_available", "horizon", "True")
        parser.add_section("telemetry")
        parser.set("telemetry", "too_slow_to_test", "False")
        parser.add_section("volume")
        parser.set("volume", "catalog_type", "volume")
        parser.set("volume", "build_interval", "10")
        parser.set("volume", "build_timeout", "300")
        parser.set("volume", "disk_format", "raw")
        parser.set("volume", "volume_size", "1")
        parser.add_section("volume-feature-enabled")
        parser.set("volume-feature-enabled", "backup", "False")
        parser.set("volume-feature-enabled", "snapshot", "True")
        parser.set("volume-feature-enabled", "api_extensions", "all")
        parser.set("volume-feature-enabled", "api_v1", "True")
        parser.set("volume-feature-enabled", "api_v2", "True")
        parser.add_section("object-storage")
        parser.set("object-storage", "container_sync_timeout" ,"120")
        parser.set("object-storage", "container_sync_interval" ,"5")
        parser.set("object-storage", "accounts_quotas_available" ,"True")
        parser.set("object-storage", "container_quotas_available" ,"True")
        parser.set("object-storage", "operator_role" ,"SwiftOperator")
        parser.add_section("orchestration")
        parser.set("orchestration", "catalog_type", "orchestration")
        parser.set("orchestration", "build_timeout" ,"300")
        parser.set("orchestration", "instance_type" ,"m1.micro")
        parser.set("orchestration", "max_template_size", "524288")
        parser.add_section("boto")
        parser.set("boto", "ec2_url", "http://%s:8773/services/Cloud" % data["ip"])
        parser.set("boto", "s3_url", "http://%s:3333" % data["ip"])
        parser.set("boto", "s3_materials_path", "/opt/stack/devstack/files/images/s3-materials/cirros-0.3.1")
        parser.set("boto", "ari_manifest", "cirros-0.3.1-x86_64-initrd.manifest.xml")
        parser.set("boto", "ami_manifest", "cirros-0.3.1-x86_64-blank.img.manifest.xml")
        parser.set("boto", "aki_manifest", "cirros-0.3.1-x86_64-vmlinuz.manifest.xml")
        parser.set("boto", "instance_type", "m1.tiny")
        parser.set("boto", "http_socket_timeout", "5")
        parser.set("boto", "num_retries ", "1")
        parser.set("boto", "build_timeout", "120")
        parser.set("boto", "build_interval", "1")

        return parser

    def config(self):
        return self.create_config_file(self.create_config())

def parse_config(o):
    config = {}
    # IP or openrc in arguments have high priority
    if 'OS_AUTH_URL' in os.environ and not (o.ip or o.openrc):
        config["OS_AUTH_URL"] = os.environ['OS_AUTH_URL']
        config["OS_TENANT_NAME"] = os.environ['OS_TENANT_NAME']
        config["OS_USERNAME"] = os.environ['OS_USERNAME']
        config["OS_PASSWORD"] = os.environ['OS_PASSWORD']
        config["OS_REGION_NAME"] = os.environ['OS_REGION_NAME']
    elif o.openrc:
        text = o.openrc.read()
        o.openrc.close()
        export_lines = (i for i in text.split("\n") if env_re.search(i))
        os_vars = (env_re.search(i).group(1) for i in export_lines)
        config = dict(((z.replace("'", "").replace('"', '') for z in  i.split("=")) for i in os_vars))
    elif o.ip:
        if o.user and o.password:
            web = OSWebCreds(o.ip, o.user, o.password)
            config = web.creds()
        else:
            web = OSWebCreds(o.ip, DEFAULT_USER, DEFAULT_PASS)
            config = web.creds()
        if config is None:
            print "Can not download WEB credentials!"
            sys.exit(1)
    else:
        print "No credentials are provided!"
        sys.exit(1)
    config["ipv"] = 4 if o.ipv == 4 else 6
    cur_dir = os.path.join(os.path.dirname(__file__))
    if os.path.exists(os.path.join(cur_dir, "..", "external_net")):
        with open(os.path.join(cur_dir, "..", "external_net")) as f:
            config["external_net"] = f.read()
    else:
        if o.ipv == 4:
            config["external_net"] = "10.10.10"
        else:
            config["external_net"] = "2002::"
    print "Configuring Openstack tempest with options below:\n%s" % str(config)
    return config

DESCRIPTION = 'reconfigure devstack to be used for tempest'
def define_cli(p):
    p.add_argument('-o', action='store', dest='openrc', type=argparse.FileType('r'), default=None,
                    help='Openrc configuration file')
    p.add_argument('-i', action='store', dest='ip',
                    help='IP address of Openstack instalaltion for downloading credentials')
    p.add_argument('-u', action='store', dest='user', default="admin",
                    help='Admin username of Openstack instalaltion for downloading credentials')
    p.add_argument('-p', action='store', dest='password', default="Cisco123",
                    help='Admin password of Openstack instalaltion for downloading credentials')
    p.add_argument('-a', action='store', dest='ipv', type=int, default=4, choices=[4, 6],
                    help='IP version for configuration: 4 or 6')
    p.add_argument('-n', action='store_true', dest='unconfig', default=False,
                    help="Remove tempest configuration from Openstack only, don't configure")
    p.add_argument('--output-file', action='store', dest='output', default="./tempest.conf.jenkins",
                    help="Name of output file to write configuration to")
    p.add_argument('-l', '--alt-image', dest='is_alt_image', type=bool, default=False,
                    help="Do we need to register the ubuntu image in addition to cirros")
    p.add_argument('--version', action='version', version='%(prog)s 1.0')
    p.set_defaults(func=main)


def main(args):
    options = parse_config(args)
    tempest = Tempest(options)
    tempest.unconfig()
    if not args.unconfig:
        if args.is_alt_image:
            IMAGES['alt_image_key'] = 'image_ref_alt'
        file = tempest.config()
        with open(args.output, "w") as f:
            file.write(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    define_cli(parser)
    args = parser.parse_args()
    args.func(args)
