import os
import time
from fabric.api import task, local, env
from common import timed, virtual
from common import logger as log
from tempest import prepare_devstack, run_tests, run_remote_tests
from fabs import LAB, IMAGES_REPO, DEVSTACK_DISK, GLOBAL_TIMEOUT, DEFAULT_SETTINGS
from snap import destroy, create

env.update(DEFAULT_SETTINGS)

__all__ = ['prepare', 'install', 'setup',
           'run_test_original_file', 'run_test_custom_file',
           'run_test_ready_file', 'run_test_remote',
           'snapshot_create']


@task
@timed
@virtual
def prepare(topology='devstack'):
    ''' Prepare VMs of specific topology for Openstack '''
    log.info("Preparing boxes for %s Openstack" % topology)
    log.info("Preparing virtual machines for lab=%s" % LAB)
    url = IMAGES_REPO + DEVSTACK_DISK
    local("test -e %s || wget -nv %s" % (DEVSTACK_DISK, url))
    local("python ./tools/cloud/create.py  -l {lab} -s /opt/imgs "
          "-z ./{disk} -t {topo} > config_file".format(lab=LAB,
                                                       disk=DEVSTACK_DISK,
                                                       topo=topology))


@task
@timed
@virtual
def install(user='localadmin', password='ubuntu'):
    ''' Install devstack Openstack on prepared environment '''
    log.info("Installing devstack Openstack")
    tempest_repo = os.environ.get("TEMPEST_REPO", "")
    tempest_br = os.environ.get("TEMPEST_BRANCH", "")
    local("python ./tools/deployers/install_devstack.py "
          "-c config_file  -u {user} -p {password} -r {repo} -b {br}".format(
        user=user,
        password=password,
        repo=tempest_repo,
        br=tempest_br
    ))


@task
@timed
def setup(topology='devstack', user='localadmin', password='ubuntu'):
    ''' Prepare and install devstack Openstack '''
    log.info("Full install of devstack Openstack")
    prepare(topology=topology)
    time.sleep(GLOBAL_TIMEOUT)
    install(topology=topology, user=user, password=password)


@task(alias='orig')
def run_test_original_file(private=True):
    ''' Copy tempest configuration from devstack installation and run tests with it locally '''
    prepare_devstack(web=False, copy=True, remote=False, private=private)
    run_tests()


@task(alias='custom')
def run_test_custom_file(private=True):
    ''' Configure tempest on devstack with custom configuration and run tests with newly created file locally '''
    prepare_devstack(web=True, copy=False, remote=False, private=private)
    run_tests()


@task(alias='ready')
def run_test_ready_file(private=True):
    ''' Use existing tempest configuration file in current directory and run tests with it locally '''
    prepare_devstack(web=False, copy=False, remote=False, private=private)
    run_tests()


@task(alias='remote')
def run_test_remote(private=True):
    ''' Use existing tempest configuration file on devstack box and run tests with it remotely '''
    prepare_devstack(web=False, copy=False, remote=True, private=private)
    run_remote_tests()


@task
@timed
def snapshot_create():
    ''' Create snapshot for devstack '''
    destroy()
    setup()
    create()
