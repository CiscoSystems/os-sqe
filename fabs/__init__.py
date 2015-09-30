import os


def read_config_from_file(yaml_path):
    import os
    import yaml
    if not os.path.isfile(yaml_path):
        raise IOError('{0} not found. Provide full path to your yaml config file'.format(yaml_path))
    with open(yaml_path) as f:
        return yaml.load(f)


class LabIds(object):
    # default lab IDs to be used by fabric tasks

    devstak_multinode = 65
    devstack_aio6 = 52
    devstack_neutron = 55
    devstack_mercury = 59
    plus_dibbler = 10
    plus_dhcp6 = 11

    redhat_aio6 = 61
    redhat_aio46 = 62
    redhat_mercury = 63
    redhat_baremetal_g8 = 64
    ucsm = 77
    ucsm_g10 = 92
    devstack_neutron_46 = 66
    devstack_aio_46 = 67



DEFAULT_SETTINGS = {"host_string": "localhost",
                    "abort_on_prompts": True,
                    "warn_only": True}

IMAGES_REPO = os.getenv('IMAGES_REPO', "http://172.29.173.233/")
UBUNTU_URL_CLOUD = "http://cloud-images.ubuntu.com/trusty/current/"
UBUNTU_DISK = "trusty-server-cloudimg-amd64-disk1.img"
CENTOS65_DISK = "centos-6.5.x86_64.qcow2"
CENTOS7_DISK = "centos-7.x86_64.qcow2"
FEDORA20_DISK = "fedora-20.x86_64.qcow2"
RHEL7_DISK = "rhel-7.x86_64.qcow2"
CUR_DIR = os.path.dirname(__file__)
REPO_DIR = os.path.abspath(os.path.join(CUR_DIR, '..'))
HOME_DIR = os.getenv('HOME')
SSH_KEY = os.path.normpath(os.path.join(
    CUR_DIR, "..", "tools", "libvirt-scripts", "id_rsa"))
GLOBAL_TIMEOUT = 180


def _get_workspace():
    if "WORKSPACE" not in os.environ:
        return os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                ".."))
    else:
        return os.environ["WORKSPACE"]


def _get_tempest_dir():
    return os.path.join(
        _get_workspace(),
        "tempest")


LAB = os.environ.get("LAB", "lab1")
QA_WAITTIME = os.environ.get("QA_WAITTIME", "18000")
QA_KILLTIME = os.environ.get("QA_KILLTIME", str(int(QA_WAITTIME) + 60))
OS_TEST_TIMEOUT = os.environ.get("OS_TEST_TIMEOUT", '')
WORKSPACE = _get_workspace()

REDHAT_DISK = os.environ.get("REDHAT_DISK", None)
COI_DISK = os.environ.get("UBUNTU_DISK", UBUNTU_DISK)
DEVSTACK_DISK = os.environ.get("DEVSTACK_DISK", UBUNTU_DISK)
DEVSTACK_CONF = os.path.normpath(os.path.join(
    CUR_DIR, "..", "tools", "deployers", "devstack-configs"))

TEMPEST_DIR = _get_tempest_dir()
TVENV = ".venv"
# Local virtualenv, that is removed every build
TLVENV = os.path.normpath(os.path.join(TEMPEST_DIR, TVENV))
# Common virtualenv for tempest in HOME
TCVENV = os.path.join(os.path.expanduser("~"), TVENV)


def _get_tempest_virtenv():
    if os.path.exists(TLVENV):
        return TLVENV
    return TCVENV


VENV = ".env"
# Local virtualenv, that is removed every build
LVENV = os.path.normpath(os.path.join(CUR_DIR, "..", VENV))
# Common virtualenv in HOME, that is persistent
CVENV = os.path.join(os.path.expanduser("~"), VENV)


def _get_virtenv():
    if os.path.exists(LVENV):
        return LVENV
    return CVENV


TEMPEST_VENV = _get_tempest_virtenv()
CUR_ENV = _get_tempest_virtenv()
