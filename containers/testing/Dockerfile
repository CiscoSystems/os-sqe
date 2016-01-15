FROM registry.access.redhat.com/rhel
MAINTAINER Dmitry Ratushnyy <dratushn@cisco.com>

RUN yum -y update; yum clean all
RUN yum -y install git python-setuptools curl ftp
# Install dependencies
RUN yum -y install automake make autoconfi gcc gcc-c++
RUN yum -y install libxml2-devel libxslt-devel lib32z1-devel
RUN yum -y install python2.7-devel python-devel libssl-devel
RUN yum -y install libxml2-python libxslt1-devel libsasl2-devel
RUN yum -y install libsqlite3-devel libldap2-devel libffi-devel
RUN yum -y install openssl-devel openssh-server
RUN yum -y install gmp-devel postgresql-devel wget
RUN yum -y install redhat-rpm-config
RUN yum -y install iputils
RUN yum -y install screen vim

RUN echo 'root:toor'| chpasswd
#ssh config
RUN mkdir /var/run/sshd
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
RUN /usr/bin/ssh-keygen -A

#setup tempest
RUN useradd tempest
RUN echo 'tempest:tempest'| chpasswd
RUN git clone -b proposed  https://github.com/cisco-openstack/tempest.git
RUN easy_install pip
RUN pip install -r /tempest/requirements.txt
RUN pip install -r /tempest/test-requirements.txt
RUN mkdir /etc/tempest
RUN cp /tempest/etc/accounts.yaml.sample  /etc/tempest/accounts.yaml

#settup cloud99
RUN git clone https://cloud-review.cisco.com/mercury/cloud99
RUN pip install -r cloud99/requirements.txt
RUN curl https://raw.githubusercontent.com/openstack/rally/master/install_rally.sh | bash

#cloud99 charts
EXPOSE 8090
EXPOSE 22
CMD [ "/usr/sbin/sshd", "-D"]
