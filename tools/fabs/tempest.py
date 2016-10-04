import os
import time
from fabric.api import task, local, env, lcd, get, settings
from common import timed, intempest, virtual, get_lab_vm_ip
from common import logger as log
from fabs import TEMPEST_DIR, QA_WAITTIME, QA_KILLTIME, WORKSPACE, DEFAULT_SETTINGS, TCVENV, OS_TEST_TIMEOUT

__all__ = ['test', 'init', 'prepare_coi', 'prepare', 'prepare_devstack',
           'prepare_with_ip', 'run_tests', 'run_remote_tests']

env.update(DEFAULT_SETTINGS)
TESTS_FILE = os.path.join(WORKSPACE, "openstack-sqe", "tools",
                          "tempest-scripts", "tests_set")


@task
@timed
@intempest
def test():
    ''' For testing purposes only '''
    log.info("Tempest test!")
    local("which python")


@task
@timed
def venv(private=True):
    log.info("Installing virtualenv for tempest")
    install = os.path.join(TEMPEST_DIR, "tools", "install_venv.py")
    wraps = ''
    if not private:
        wraps = "export venv=%s; " % TCVENV
    local("%spython " % wraps + install)


@task
@timed
@intempest
def additions():
    log.info("Installing additional modules for tempest")
    local("pip install junitxml nose")


@task
@timed
def init(private=False):
    ''' Initialize tempest - virtualenv, requirements '''
    venv(private=private)
    additions()


@task
@timed
@virtual
def prepare(openrc=None, ip=None, ipv=None, add=None):
    ''' Prepare tempest '''
    if ip:
        args = " -i " + ip
    elif openrc:
        args = " -o " + openrc
    else:
        raise NameError("Provide either IP or openrc file!")
    if ipv:
        args += " -a " + ipv
    if add:
        args += " " + add
    local("python ./tools/tempest_configurator.py %s" % args)


@task
@timed
def prepare_coi(topology=None, copy=False, private=True):
    ''' Prepare tempest especially for COI '''
    log.info("Preparing tempest for COI")
    init(private=private)
    if copy:
        ip = get_lab_vm_ip()
        with settings(host_string=ip, user='root',
                      abort_on_prompts=True, warn_only=True):
            get("/root/openrc", "./openrc")
    prepare(openrc="./openrc")
    if topology == "2role":
        local("sed -i 's/.*[sS]wift.*\=.*[Tt]rue.*/swift=false/g' ./tempest.conf.jenkins")
    conf_dir = os.path.join(TEMPEST_DIR, "etc")
    local("mv ./tempest.conf.jenkins %s/tempest.conf" % conf_dir)


@task(alias='dev')
@timed
def prepare_devstack(web=True, copy=False, remote=False, private=True):
    ''' Prepare tempest for devstack '''
    if remote:
        return
    init(private=private)
    conf_dir = os.path.join(TEMPEST_DIR, "etc")
    if copy:
        log.info("Copying tempest configuration from devstack")
        ip = get_lab_vm_ip()
        with settings(host_string=ip, abort_on_prompts=True, warn_only=True):
            get("/opt/stack/tempest/etc/tempest.conf", "./tempest.conf")
    if not web:
        log.info("Preparing tempest for devstack with ready file")
        local("mv ./tempest.conf %s/tempest.conf" % conf_dir)
    else:
        ip = get_lab_vm_ip()
        log.info("Preparing tempest for devstack with IP: %s" % ip)
        RETRY = 3
        for _ in xrange(RETRY):
            prepare(ip=ip)
            cmd = local("mv ./tempest.conf.jenkins %s/tempest.conf" % conf_dir)
            if cmd.failed:
                time.sleep(10)
            else:
                break



@task(alias='ip')
@timed
def prepare_with_ip(private=True):
    ''' Prepare tempest with IP of Horizon: for RedHat, etc '''
    log.info("Preparing tempest configuration by downloading openrc from Horizon")
    init(private=private)
    ip = get_lab_vm_ip()
    prepare(ip=ip)
    conf_dir = os.path.join(TEMPEST_DIR, "etc")
    local("mv ./tempest.conf.jenkins %s/tempest.conf" % conf_dir)


@task(alias="run")
@timed
@intempest
def run_tests(force=True, parallel=False):
    ''' Run Tempest tests locally '''
    log.info("Run Tempest tests")
    time_prefix = "timeout --preserve-status -s 2 -k {kill} {wait} ".format(
        wait=QA_WAITTIME, kill=QA_KILLTIME)
    with lcd(TEMPEST_DIR):
        repo_exists = os.path.exists(os.path.join(TEMPEST_DIR, ".testrepository"))
        if parallel:
            testrun = "testr run --parallel "
        else:
            testrun = "testr run "
        if repo_exists and not force:
            log.info("Tests have already run, now run the failed only")
            cmd = "%s --failing --subunit | subunit-2to1 | tools/colorizer.py" % testrun
        else:
            if repo_exists:
                local("rm -rf .testrepository")
            local("testr init")
            if os.path.getsize(TESTS_FILE) > 0:
                log.info("Tests haven't run yet, run them from file %s" % TESTS_FILE)
                cmd = '%s --load-list %s --subunit  | subunit-2to1 | tools/colorizer.py' % (testrun, TESTS_FILE)
            else:
                regex = os.environ.get('REG', "")
                log.info("Tests haven't run yet, run them with regex: '%s'" % regex)
                cmd = "%s \"%s\" --subunit | subunit-2to1 | tools/colorizer.py" % (testrun, regex)
        local(time_prefix + cmd)
        result = os.path.join(WORKSPACE, "openstack-sqe", "nosetests_" + time.strftime("%H%M%S") + ".xml")
        subunit = os.path.join(WORKSPACE, "openstack-sqe", "testr_results.subunit")
        fails_extract = os.path.join(WORKSPACE, "openstack-sqe", "tools",
                                     "tempest-scripts", "extract_failures.py")
        local("testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=%s" % result)
        local("testr last --subunit > %s" % subunit)
        local("python {script} {result} > {tests_file}".format(
            script=fails_extract, result=result, tests_file=TESTS_FILE))


@task(alias="remote")
@timed
@virtual
def run_remote_tests():
    ''' Run Tempest tests remotely'''
    log.info("Run Tempest tests remotely")
    tempest_repo = os.environ.get("TEMPEST_REPO", "")
    tempest_br = os.environ.get("TEMPEST_BRANCH", "")
    tempest_patch_set = os.environ.get("TEMPEST_PATCHSET", "")
    ip = get_lab_vm_ip()
    test_regex = os.environ.get('REG', "")
    args = ""
    if os.path.getsize(TESTS_FILE) > 0:
        log.info("Run tests from file %s" % TESTS_FILE)
        args = " -l %s " % TESTS_FILE
    elif test_regex:
        log.info("Run tests with regex: '%s'" % test_regex)
        args = " -f \"%s\" " % test_regex
    else:
        log.info("Run all tests for devstack")
    local('python {wrk}/openstack-sqe/tools/run_tempest.py -r {ip} '
          '{args} --repo {repo} --branch {br} -v --kill_time {kill_time} '
          '--wait_time {wait_time} --test_time {test_time} --patchset {ps}'.format(
        wrk=WORKSPACE, ip=ip, args=args, repo=tempest_repo,
        br=tempest_br, kill_time=QA_KILLTIME, wait_time=QA_WAITTIME,
        test_time=OS_TEST_TIMEOUT, ps=tempest_patch_set))


@task
@timed
def create_tempest_conf(cloud_controller_ip):
    from os_inspector import OS

    os_inspector = OS(ip=cloud_controller_ip)
    os_inspector.create_tempest_conf()
