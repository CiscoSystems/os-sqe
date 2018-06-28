os-sqe: deployment, scaling, performance studies and other QA automation tasks
=============

The recommended way to use is to run the container:

    docker run -it --name os-sqe-fab --rm -v $PWD:/os-sqe:ro  -v $HOME/artifacts:/tmp cloud-docker.cisco.com/os-sqe:2.7 <your command>

Here:
    -v $PWD:/os-sqe:ro is to mount your current repo sandbox
    -v $HOME/artifacts:/tmp is to collect all artifacts created by run in container's /tmp


By default, container runs fab -l (entry point is /usr/local/bin/fab and cmd is -l)


If you want to run python manually:

        docker run -it --name os-sqe-python --entrypoint python --rm -v $PWD:/os-sqe:ro  -v $HOME/artifacts:/tmp cloud-docker.cisco.com/os-sqe:2.7

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
