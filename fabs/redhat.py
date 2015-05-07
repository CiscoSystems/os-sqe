import time
from fabric.api import task, local, env
from common import timed, virtual
from common import logger as log
from tempest import prepare_with_ip, run_tests
from fabs import LAB, IMAGES_REPO, CENTOS65_DISK, CENTOS7_DISK, FEDORA20_DISK, \
    REDHAT_DISK, GLOBAL_TIMEOUT, DEFAULT_SETTINGS, RHEL7_DISK

env.update(DEFAULT_SETTINGS)


@task
@timed
@virtual
def prepare(topo, distro="centos7"):
    """ Spin out libvirt VM(s) based on given distro """
    log.info("Preparing virtual machines for lab=%s" % LAB)
    disk = REDHAT_DISK
    if not disk:
        disk = {
            'centos7': CENTOS7_DISK,
            'centos65': CENTOS65_DISK,
            'fedora20': FEDORA20_DISK,
            'rhel7': RHEL7_DISK
        }.get(distro, None)
        if not disk:
            raise NameError("Please choose distro from 'centos7', 'centos65',"
                            " 'fedora20', 'rhel7'")
    topo_file = {
        "aio": "aio_rh_topology.yaml",
        "2role": "rh_2role_topology.yaml",
        "3role": "rh_3role_topology.yaml"
    }.get(topo, None)
    if not topo_file:
        raise NameError("Please choose topology from 'aio', '2role', '3role'")
    log.info("Running {topo} Openstack with distro {disk}".format(topo=topo, disk=disk))
    url = IMAGES_REPO + disk
    local("test -e %s || wget -nv %s" % (disk, url))
    local("python ./tools/cloud/create.py -l {lab} -s /opt/imgs "
          "-z ./{disk} -r redhat -c "
          "./tools/cloud/cloud-configs/{topo} > "
          "config_file".format(lab=LAB,
                               disk=disk,
                               topo=topo_file))


@task
@timed
@virtual
def install(topology, waittime=10000):
    ''' Install Openstack  with Packstack: aio, 2role, 3role '''
    killtime = waittime + 60
    if topology == "2role":
        args = "-t 2role"
    elif topology == "3role":
        args = "-t 3role"
    elif topology == "aio":
        args = ""
    else:
        raise NameError("Please choose topology from 'aio', '2role', '3role'")
    log.info("Installing %s Openstack" % topology)
    local("timeout --preserve-status -s 15 "
          "-k {killtime} {waittime} ./tools/deployers/install_aio_rh.py "
          "-c config_file -u root -p ubuntu {args}".format(
        args=args,
        waittime=waittime,
        killtime=killtime))


@task
@timed
def only_test():
    ''' Prepare and run Tempest tests '''
    log.info("Configuring Openstack for tempest")
    prepare_with_ip()
    log.info("Started testing Openstack")
    run_tests(force=False)


@task
@timed
def full(topology):
    ''' Prepare, install and test RedHat Openstack with Tempest '''
    log.info("Full install and test of %s Openstack" % topology)
    if not topology or topology not in ("aio", "2role", "3role"):
        raise NameError("Topology should be one of: 'aio', '2role', '3role'")
    prepare(topology, distro='centos7')
    time.sleep(GLOBAL_TIMEOUT)
    install(topology)
    only_test()


@task
@timed
def aio6(lab_id=51, phase='lab', cleanup=None):
    """Run tempest on aio OS deployed by RH packstack, IPv6 only"""
    from fabs.lab.lab_class import MyLab

    l = MyLab(lab_id=lab_id, topology_name='aio6_by_packstack')
    l.create_lab(phase='delete' if cleanup else phase)


@task
@timed
def aio46(lab_id=52, phase='lab', cleanup=None):
    """Run tempest on aio OS deployed by RH packstack, IPv4+6 dual-stack"""
    from fabs.lab.lab_class import MyLab

    l = MyLab(lab_id=lab_id, topology_name='aio46_by_packstack')
    l.create_lab(phase='delete' if cleanup else phase)


@task
@timed
def mercury(lab_id=55, phase='lab', cleanup=None):
    """Run tempest on mercury topo deployed by RH packstack"""
    from fabs.lab.lab_class import MyLab

    l = MyLab(lab_id=lab_id, topology_name='mercury_by_packstack')
    l.create_lab(phase='delete' if cleanup else phase)


@task
@timed
def baremetal(lab_id=77, phase='lab', cleanup=None):
    """Run tempest on mercury topo deployed by RH packstack"""
    from fabs.lab.lab_class import MyLab

    l = MyLab(lab_id=lab_id, topology_name='baremetal_by_packstack')
    l.create_lab(phase='delete' if cleanup else phase)
