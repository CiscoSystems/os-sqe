import time
from fabric.api import task, local, get, settings, sudo, run
from fabric.contrib.files import sed
from common import get_lab_vm_ip
from fabs import SSH_KEY

__all__ = ['start', 'stop']

JOB = {"host_string": None,
               "user": None,
               "password": None,
               "warn_only": True,
               "key_filename": SSH_KEY,
               "abort_on_prompts": True,
               "gateway": None}

def reformat_xml(f):
    with open(f) as fd:
        xml = fd.read()
        new = xml.replace("/opt/stack/neutron", "neutron")
        return new

@task
def start(ip=None, user="localadmin", password="ubuntu"):
    if not ip:
        ip = get_lab_vm_ip()
    JOB.update({
        "host_string":ip,
        "user": user,
        "password": password
        })
    with settings(**JOB):
        sudo("apt-get install -y python-coverage")
        run("screen -S stack -X quit")
        run("rm -rf coverage.* .coverage*")
        stack_file = '~/devstack/stack-screenrc'
        stack_cov = '~/devstack/stackcov-screenrc'
        run("cp {orig} {cov}".format(orig=stack_file, cov=stack_cov))
        sed(stack_cov, 'stuff "python', 'stuff "python-coverage run -p')
        run("screen -c {0} -d -m && sleep 1".format(stack_cov))

@task
def stop(ip=None, user="localadmin", password="ubuntu"):
    if not ip:
        ip = get_lab_vm_ip()
    JOB.update({
        "host_string":ip,
        "user": user,
        "password": password
        })
    with settings(**JOB):
        # Send SIGINT to all screen windows
        run('screen -S stack -X at "#" stuff $"\\003"')
        time.sleep(15)
        run("python-coverage combine")
        run("python-coverage xml --include '/opt/stack/neutron/*'")
        #run("python-coverage xml -o coverage_ml2.xml --include '/opt/stack/neutron/neutron/plugins/ml2/*'")
        get("coverage.xml", "./coverage.xml")
    new = reformat_xml("./coverage.xml")
    local("cp ./coverage.xml ./coverage.xml.bkp")
    with open("./coverage.xml", "w") as f:
        f.write(new)
