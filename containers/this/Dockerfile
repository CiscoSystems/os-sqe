FROM ubuntu
MAINTAINER Kirill Shileev <kshileev@cisco.com>

RUN apt-get update && apt-get install -y git python python-dev virtualenv gcc libssl-dev && git clone https://github.com/CiscoSystems/os-sqe.git && virtualenv venv && /venv/bin/pip install -r /os-sqe/requirements.txt
