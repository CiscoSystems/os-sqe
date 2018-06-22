FROM python:2.7-slim as py
MAINTAINER Kirill Shileev <kshileev@cisco.com>

ADD . /os-sqe
RUN pip install --trusted-host pypi.python.org -r /os-sqe/requirements.txt
WORKDIR /os-sqe
ENTRYPOINT ["/usr/local/bin/fab"]
CMD ["-l"]
