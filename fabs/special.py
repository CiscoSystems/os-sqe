from fabric.api import task, local
from fabs.common import timed

@task
@timed
def requirements_os(purge=False):
    """Install (or purge) all OS level packages needed for operations"""
    if purge:
        local('sudo apt-get purge -y $(cat os-packages/ubuntu)')
    else:
        local('sudo apt-get install -y $(cat os-packages/ubuntu)')
