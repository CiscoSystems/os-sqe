import os
import time
from fabric.api import task, local, env, settings, run, cd, put
from common import timed, virtual, get_lab_vm_ip
from common import logger as log
from tempest import prepare_devstack, run_tests, run_remote_tests
from fabs import LAB, IMAGES_REPO, DEVSTACK_DISK, GLOBAL_TIMEOUT, DEFAULT_SETTINGS, DEVSTACK_CONF
from fabs.lab.lab_class import MyLab
from snap import destroy, create
from fabs import LabIds

env.update(DEFAULT_SETTINGS)


@task
@timed
@virtual
def prepare(topology='devstack'):
    """ Prepare VMs of specific topology for Openstack """
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
def install(user='localadmin', password='ubuntu', devstack_config="devstack_single_node"):
    """ Install devstack Openstack on prepared environment """
    log.info("Installing devstack Openstack")
    tempest_repo = os.environ.get("TEMPEST_REPO", "")
    tempest_br = os.environ.get("TEMPEST_BRANCH", "")
    devstack_repo = os.environ.get("DEVSTACK_REPO", "")
    devstack_br = os.environ.get("DEVSTACK_BRANCH", "")
    devstack_patch = os.environ.get("DEVSTACK_PATCH", "")
    local("python ./tools/deployers/install_devstack.py "
          "-c config_file  -u {user} -p {password} -r {repo} -b {br} "
          "-e {devstack_repo} -l {devstack_br} -m {patch} "
          "--devstack_config {devstack_config}".format(
        user=user,
        password=password,
        repo=tempest_repo,
        br=tempest_br,
        devstack_repo=devstack_repo,
        devstack_br=devstack_br,
        devstack_config=os.path.join(DEVSTACK_CONF, devstack_config + ".yaml"),
        patch=devstack_patch
    ))


@task
@timed
def setup(topology='devstack', devstack_config="devstack_single_node", user='localadmin', password='ubuntu'):
    """ Prepare and install devstack Openstack """
    log.info("Full install of devstack Openstack")
    prepare(topology=topology)
    time.sleep(GLOBAL_TIMEOUT)
    install(user=user, password=password, devstack_config=devstack_config)


@task(alias='orig')
def run_test_original_file(private=True):
    """ Copy tempest configuration from devstack installation and run tests with it locally """
    prepare_devstack(web=False, copy=True, remote=False, private=private)
    run_tests()


@task(alias='custom')
def run_test_custom_file(private=True):
    """ Configure tempest on devstack with custom configuration and run tests with newly created file locally """
    prepare_devstack(web=True, copy=False, remote=False, private=private)
    run_tests()


@task(alias='ready')
def run_test_ready_file(private=True):
    """ Use existing tempest configuration file in current directory and run tests with it locally """
    prepare_devstack(web=False, copy=False, remote=False, private=private)
    run_tests()


@task(alias='remote')
def run_test_remote(private=True):
    """ Use existing tempest configuration file on devstack box and run tests with it remotely """
    prepare_devstack(web=False, copy=False, remote=True, private=private)
    run_remote_tests()


@task
@timed
def snapshot_create():
    """ Create snapshot for devstack """
    destroy()
    setup()
    create()


@task
@timed
def set_branch(component="neutron", branch="master"):
    """ Set Openstack component for particular branch or commit """
    ip = get_lab_vm_ip()
    with settings(host_string=ip, abort_on_prompts=True, warn_only=True):
        stack_file = '~/devstack/stack-screenrc'
        run("screen -S stack -X quit")
        path = os.path.join("/opt", "stack", component)
        with cd(path):
            run("git fetch --all; git checkout {br}".format(br=branch))
        run("screen -c {0} -d -m && sleep 1".format(stack_file))


@task
@timed
def patchset(component="neutron", patch_set=None):
    """ Set Openstack component for particular patchset of Gerrit """
    ip = get_lab_vm_ip()
    if not patch_set:
        raise Exception("Please provide patchset as 'refs/changes/44/129144/1'")
    with settings(host_string=ip, abort_on_prompts=True, warn_only=True):
        stack_file = '~/devstack/stack-screenrc'
        run("screen -S stack -X quit")
        path = os.path.join("/opt", "stack", component)
        with cd(path):
            run("git fetch https://review.openstack.org/openstack/{project}"
                " {patchset} && git checkout FETCH_HEAD".format(
                project=component,
                patchset=patch_set))
        run("screen -c {0} -d -m && sleep 1".format(stack_file))


def determine_configuration(ip='localhost'):
    with settings(host_string=ip):
        folder = os.path.dirname(run('find ~ -name stack.sh'))
        dest = run('grep -E "^DEST=(.+)$" {0}/local.conf {0}/stackrc | cut -d = -f2'.format(folder))

    d = {'folder': folder, 'DEST': dest.split()[0], 'screen': folder + '/stack-screenrc'}
    log.info(d)
    return d


@task
@timed
def apply_patches(component='neutron', from_folder='~/patches', ip='localhost'):
    """ Apply all patches found in the given directory to the given component """
    cfg = determine_configuration(ip=ip)
    uploaded_folder = '~/uploaded_patches'
    with settings(host_string=ip):
        run('mkdir -p ' + uploaded_folder)
        put(local_path=from_folder + '/*.patch', remote_path=uploaded_folder)
        with cd(cfg['DEST'] + '/' + component):
            run('git checkout -- .')
            run('git checkout master')
            for name in run('ls {0}/*.patch'.format(uploaded_folder)).split():
                run('patch -p1 < ' + name)
    restart_screen(ip=ip)


def restart_screen(ip='localhost', screen_cfg=None):
    """ (Re)start screen with all OS processes attached to it """
    screen_cfg = screen_cfg or determine_configuration(ip=ip)['screen']
    with settings(host_string=ip, abort_on_prompts=True, warn_only=True):
        run('screen -S stack -X quit && sleep 5')
        run('screen -c {0} -d -m && sleep 1'.format(screen_cfg))


def lab_create_delete(lab_obj, phase, cleanup):
    if not cleanup != 'do not cleanup':
        lab_obj.create_lab(phase=phase)
    else:
        lab_obj.delete_lab()


@task
@timed
def plus_dhcp6(lab_id=LabIds.plus_dhcp6, phase='lab', devstack_conf_addon='', cleanup='do not cleanup'):
    """aio + dhcp6 server in separate VMs"""
    lab = MyLab(lab_id=lab_id, topology_name='devstack_aio_plus_dhcp6', devstack_conf_addon=devstack_conf_addon)
    lab_create_delete(lab, phase, cleanup)


@task
@timed
def plus_dibbler(lab_id=LabIds.plus_dibbler, phase='lab', cleanup='do not cleanup'):
    """aio + dibbler server in separate VMs"""
    lab = MyLab(lab_id=lab_id, topology_name='devstack_aio_plus_dibbler')
    lab_create_delete(lab, phase, cleanup)


@task
@timed
def plus_nxos(phase='lab', cleanup='do not cleanup'):
    """abc + compute, Cisco ML2 with external nxos switch"""
    lab = MyLab(lab_id=77, topology_name='devstack_abc_compute_plus_nxos')
    lab_create_delete(lab, phase, cleanup)


@task
@timed
def neutron(lab_id=LabIds.devstack_neutron,  cleanup='do not cleanup'):
    """Run single machine with neutron only"""

    lab = MyLab(lab_id=lab_id, topology_name='neutron6',)
    lab_create_delete(lab_obj=lab, phase='lab', cleanup=cleanup)


@task
@timed
def mercury(lab_id=LabIds.devstack_mercury,  cleanup='do not cleanup'):
    """Run reference topology for Mercury"""

    lab = MyLab(lab_id=lab_id, topology_name='mercury',)
    lab_create_delete(lab_obj=lab, phase='lab', cleanup=cleanup)


@task
@timed
def aio6(lab_id=LabIds.devstack_aio6,  cleanup='do not cleanup'):
    """Run all in one OS deployed on v6 only virtual host"""

    lab = MyLab(lab_id=lab_id, topology_name='aio6',)
    lab_create_delete(lab_obj=lab, phase='lab', cleanup=cleanup)


@task
@timed
def multinode(lab_id=LabIds.devstak_multinode, cleanup='do not cleanup'):

    """Deploy devstack multinode: 1 all-but-compute, 3 computes"""

    lab = MyLab(lab_id=lab_id, topology_name='devstack_multinode')
    lab_create_delete(lab_obj=lab, phase='lab', cleanup=cleanup)
