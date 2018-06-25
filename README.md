os-sqe: deployment, scaling, performance studies and other QA automation tasks
=============

The recommended way to use is to run the container:

    docker run --name os-sqe --rm cloud-docker.cisco.com/os-sqe:2.7 <task_name:task_argument1,task_argument2,...>

By default, container runs fab -l

To build docker image, do:

    git clone https://github.com/CiscoSystems/os-sqe.git
    cd os-sqe
    docker build -t cloud-docker.cisco.com/os-sqe:2.7 .

To push image to registry:

    docker push cloud-docker.cisco.com/os-sqe:2.7

In case you don't have docker, manual way to operate:

    git clone https://github.com/CiscoSystems/os-sqe.git
    cd os-sqe
    virtualenv .venv
    . .venv/bin/activate
    pip install -r requirements.txt

Making Changes
---------------

We are using normal GitHub process. Fork this repo, create a branch and suggest new pull request.
See details here: https://guides.github.com/activities/contributing-to-open-source/#contributing
