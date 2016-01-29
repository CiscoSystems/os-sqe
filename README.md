openstack-sqe
=============

To get this repo prepared for operation, the recommended way is:

    virtualenv .venv > artefacts/venv-pip-log.txt 2>&1
    . .venv/bin/activate >> artefacts/venv-pip-log.txt 2>&1
    pip install -r requirements.txt >> artefacts/venv-pip-log.txt 2>&1

The main part of the code is decorated as fabric tasks and might be executed by:

    fab task_name:task_argument1,task_argument2

The list of tasks is produced by:

    fab -l