openstack-sqe is a repo for deployment and QA related tasks automation
=============

To get this repo prepared for operation, the recommended way is:

    virtualenv .venv
    . .venv/bin/activate
    pip install -r requirements.txt

The main part of the code is decorated as fabric tasks and might be executed by:

    fab task_name:task_argument1,task_argument2

The list of tasks is produced by:

    fab -l


Making Changes
---------------

We are using normal GitHub process. Fork this repo, create a branch and suggest new pull request.
See details here: https://guides.github.com/activities/contributing-to-open-source/#contributing
