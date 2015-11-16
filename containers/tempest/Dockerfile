FROM registry.access.redhat.com/rhel
MAINTAINER Clifford Baeseman <cbaesema@cisco.com>

RUN yum -y update; yum clean all

# Install git, python and essential tools
RUN yum install -y git python-setuptools curl ftp
RUN easy_install pip

# Install dependencies
RUN yum -y install automake make autoconfi gcc gcc-c++
RUN yum -y install libxml2-devel libxslt-devel lib32z1-devel
RUN yum -y install python2.7-devel python-devel libssl-devel
RUN yum -y install libxml2-python libxslt1-devel libsasl2-devel
RUN yum -y install libsqlite3-devel libldap2-devel libffi-devel
RUN yum -y install openssl-devel
RUN yum -y install vim
RUN yum install -y iputils #contains

# Setup Environment by Cloning tempest
RUN git clone https://github.com/cisco-openstack/tempest.git
WORKDIR /tempest
RUN git checkout proposed
# installing tempest dependencies
RUN pip install -r /tempest/requirements.txt
RUN pip install -r /tempest/test-requirements.txt

# Copy sample configuration
RUN mkdir /etc/tempest
RUN cp /tempest/etc/accounts.yaml.sample  /etc/tempest/accounts.yaml

COPY ./config_tempest.py /tempest/tools/config_tempest.py
COPY ./api_discovery.py /tempest/tempest/common/api_discovery.py
COPY ./default-overrides.conf  /tempest/etc/default-overrides.conf
WORKDIR /tempest
RUN python tools/config_tempest.py --create
ENTRYPOINT ["/usr/bin/ostestr"]
