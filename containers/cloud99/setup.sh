#!/usr/bin/env bash
yum -y update; yum clean all
yum -y install redhat-rpm-config

yum install -y git python-setuptools

easy_install pip

# Install dependencies
yum -y install automake make autoconfi gcc gcc-c++
yum -y install libxml2-devel libxslt-devel lib32z1-devel
yum -y install python2.7-devel python-devel libssl-devel
yum -y install libxml2-python libxslt1-devel libsasl2-devel
yum -y install libsqlite3-devel libldap2-devel libffi-devel
yum -y install openssl-devel
yum -y install gmp-devel postgresql-devel wget
yum -y install vim
yum -y install openssh-server
yum -y install screen

#User configs
USER_PASSWORD='cisco123'
echo 'root:'$USER_PASSWORD | chpasswd
useradd cloud99
echo 'cloud99:'$USER_PASSWORD | chpasswd

#SSHD configs
mkdir /var/run/sshd
sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
/usr/bin/ssh-keygen -A

#SETUP Cloud99
su cloud99
git clone https://cloud-review.cisco.com/mercury/cloud99
pip install -r cloud99/requirements.txt
/bin/bash -c "curl https://raw.githubusercontent.com/openstack/rally/master/install_rally.sh | bash"

