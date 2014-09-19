import time
from fabric.api import task, local, env
from common import timed, virtual
from common import logger as log
from tempest import prepare_coi, run_tests
from snap import destroy, create
from fabs import LAB, IMAGES_REPO, COI_DISK, UBUNTU_URL_CLOUD, GLOBAL_TIMEOUT, DEFAULT_SETTINGS

__all__ = ['prepare', 'install', 'role2', 'snapshot_create',
           'aio', 'fullha', 'only_test', 'full']

env.update(DEFAULT_SETTINGS)


@task
@timed
@virtual
def prepare_vms(topo, args='', cloud=False):
    log.info("Preparing virtual machines for lab=%s" % LAB)
    if cloud:
        url = UBUNTU_URL_CLOUD + COI_DISK
    else:
        url = IMAGES_REPO + COI_DISK
    local("test -e %s || wget -nv %s" % (COI_DISK, url))
    local("python ./tools/cloud/create.py  -l {lab} -s /opt/imgs "
          "-z ./{disk} -t {topo} {args} > config_file".format(lab=LAB,
                                                              disk=COI_DISK,
                                                              topo=topo,
                                                              args=args))


@task
def prepare(topology, cobbler=False, cloud=False):
    ''' Prepare VMs of specific topology for Openstack '''
    log.info("Preparing boxes for %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    args = '-b net' if cobbler else ''
    prepare_vms(topology, cloud=cloud, args=args)


@task
@timed
@virtual
def install_os(script, args='', waittime=10800):
    killtime = waittime + 60
    local("timeout --preserve-status -s 15 "
          "-k {killtime} {waittime} ./tools/deployers/{script} "
          "{args} -c config_file -u root".format(
        script=script,
        args=args,
        waittime=waittime,
        killtime=killtime))


@task
def install(topology=None, cobbler=False):
    ''' Install Openstack on prepared environment '''
    if not topology or topology not in ("aio", "2role", "fullha"):
        raise NameError("Topology should be one of: 'aio', '2role', 'fullha'")
    log.info("Installing %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    args = '-e' if cobbler else ''
    if topology == "aio":
        install_os("install_aio_coi.py")
    elif topology == "2role":
        install_os("install_aio_2role.py", args=args)
        local("touch 2role")
    else:
        install_os("install_fullha.py", args=args)

@task
@timed
def aio(cloud=False):
    ''' Prepare and install All-in-One Openstack '''
    log.info("Full install of All-in-One Openstack")
    prepare("aio", cloud=cloud)
    time.sleep(GLOBAL_TIMEOUT)
    install("aio")


@task(alias='2role')
@timed
def role2(cloud=False, cobbler=False):
    ''' Prepare and install 2role Openstack '''
    log.info("Full install of 2role Openstack" + (
        " with cobbler" if cobbler else ''))
    prepare("2role", cloud=cloud, cobbler=cobbler)
    time.sleep(GLOBAL_TIMEOUT)
    install("2role", cobbler=cobbler)


@task
@timed
def fullha(cloud=False, cobbler=False):
    ''' Prepare and install Full HA Openstack '''
    log.info("Full install of Full HA Openstack" + (
        " with cobbler" if cobbler else ''))
    prepare("fullha", cloud=cloud, cobbler=cobbler)
    time.sleep(GLOBAL_TIMEOUT)
    install("fullha", cobbler=cobbler)


@task
@timed
@virtual
def workarounds():
    ''' Make workarounds for tempest after COI install '''
    local("python ./tools/tempest-scripts/tempest_align.py "
          "-c config_file -u localadmin -p ubuntu")


@task
@timed
def only_test(topology):
    ''' Prepare and run Tempest tests, provide topology: aio, 2role, fullha '''
    log.info("Configuring Openstack for tempest")
    if not topology or topology not in ("aio", "2role", "fullha"):
        raise NameError("Topology should be one of: 'aio', '2role', 'fullha'")
    prepare_coi(topology)
    run_tests(force=False)


@task
@timed
def full(topology, cobbler=False, cloud=False):
    ''' Prepare, install and test with Tempest Openstack '''
    log.info("Full install and test of %s Openstack" % topology + (
        " with cobbler" if cobbler else ''))
    if not topology or topology not in ("aio", "2role", "fullha"):
        raise NameError("Topology should be one of: 'aio', '2role', 'fullha'")
    prepare(topology, cloud=cloud, cobbler=cobbler)
    time.sleep(GLOBAL_TIMEOUT)
    install(topology, cobbler=cobbler)
    workarounds()
    only_test(topology)


@task(alias='snap')
@timed
def snapshot_create(topology=None):
    ''' Make COI installation and create snapshot from installed COI '''
    func = {
        "2role": role2,
        "aio": aio,
        "fullha": fullha,
    }.get(topology, None)
    if not func:
        raise NameError("Configuration should be one of: 'aio', '2role', 'fullha'")
    log.info("Creating snapshots for COI %s" % topology)
    destroy()
    func()
    workarounds()
    create()
