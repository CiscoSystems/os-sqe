import argparse
import os

DIR_PATH = os.path.abspath(os.path.dirname(__file__))
TOPO_PATH = os.path.join(DIR_PATH, "cloud-configs")
TEMPLATE_PATH = os.path.join(DIR_PATH, "cloud-templates")

def parse(f):
    lines = f.readlines()
    return dict([i.split("=") for i in lines])

class ConfigError(Exception):
    pass

parser = argparse.ArgumentParser()
parser.add_argument('-u', action='store', dest='user', default="root",
                    help='User to run the script with')
parser.add_argument('-a', action='store', dest='host', default="localhost",
                    help='Host for action')
parser.add_argument('-b', action='store', dest='boot', default="cloudimg",
                    choices=['net', 'cloudimg'], help='Boot')
parser.add_argument('-t', action='store', dest='topology', default=None,
                    choices=["aio", "2role", "fullha", "devstack", "standalone",
                             "aio6", "devstack6", "devstack64", "2role6", "fullha6"],
                    help='Choose topology')
parser.add_argument('-c', dest='topoconf', type=argparse.FileType('r'), default=None,
                    help='Topology configuration file')
parser.add_argument('-g', dest='defaults', type=argparse.FileType('r'), default=None,
                    help='Override defaults in this file')
parser.add_argument('-l', action='store', dest='lab_id', default="lab1",
                    help='Lab ID in configuration, default=lab1')
parser.add_argument('-r', dest='distro', choices=["ubuntu", "redhat"], default="ubuntu",
                    help='Linux distro - RedHat or Ubuntu')


parser.add_argument('-s', action='store', dest='img_dir', default="/opt/imgs",
                    help='Where to store all images and disks, full abs path')
parser.add_argument('-z', action='store', dest='cloud_img_path',
                    default="/opt/iso/trusty-server-cloudimg-amd64-disk1.img",
                    help='Where to find downloaded cloud image, full abs path')

parser.add_argument('-y', action='store_true', dest='shutdown_all', default=False,
                    help='Shutdown all VMs with this lab_id')
parser.add_argument('-x', action='store_true', dest='undefine_all', default=False,
                    help='Undefine everything with this lab_id')



opts = parser.parse_args()

if opts.topology and opts.topoconf:
    raise ConfigError("Please choose either predefined topology"
                      "or custom file")
if not opts.defaults:
    DOMAIN_NAME = "domain.name"
    DNS = "8.8.8.8"
else:
    params = parse(opts.defaults)
    DOMAIN_NAME = params["domain.name"]
    DNS = params["8.8.8.8"]
ip_order = ("devstack-server", "aio-server", "build-server", "control-server",
            "compute-server", "swift-storage", "swift-proxy", "load-balancer")
