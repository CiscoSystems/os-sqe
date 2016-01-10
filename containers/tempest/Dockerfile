FROM registry.access.redhat.com/rhel
MAINTAINER Dmitry Ratushnyy <dratushn@cisco.com>
RUN yum-config-manager --enable rhel-7-server-optional-rpms
RUN subscription-manager status
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
RUN yum install -y iputils
RUN yum -y install openssh-server

RUN useradd tempest
RUN echo 'tempest:tempest'| chpasswd
RUN echo 'root:tempest'| chpasswd
RUN mkdir /var/run/sshd
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
RUN /usr/bin/ssh-keygen -A

RUN git clone https://github.com/cisco-openstack/tempest.git
WORKDIR /tempest
RUN git checkout proposed

# installing tempest dependencies
RUN pip install -r /tempest/requirements.txt
RUN pip install -r /tempest/test-requirements.txt

# Copy sample configuration
RUN mkdir /etc/tempest
RUN cp /tempest/etc/accounts.yaml.sample  /etc/tempest/accounts.yaml

COPY ./default-overrides.conf  /tempest/etc/default-overrides.conf
WORKDIR /tempest
RUN python tools/config_tempest.py --create
EXPOSE 22
CMD [ "/usr/sbin/sshd", "-D"]
