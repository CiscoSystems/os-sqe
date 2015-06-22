#!/bin/bash

sleep 1m

WORK_DIR=`pwd`

cat >>/home/ubuntu/.ssh/authorized_keys <<EOF
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCj9HsmH5E2hlwOXpBd8FFQY0fxMBJBiFeAc/I9ds9WQMjeuLnYWICE2DCX7AoMSwPLl/IwKQZGV/Vt3nB12/EKvTMx6yCgfPOGrejzYYUhDSxJwuFg5KHDuLHXcUjDz/uAn2mzEDwPqtsxRSeKB/IYa7cn2VdgmrIi7PPc2/Gzk7CnYpqwMjMr1A9BxJz41yCN4gkNxk8LFxVtiAFQRuPVAU06yzEbQHPzPCZbVOpBo+TZcEOIepCy0DLrjcwEa26uBEeN13aGWaRuhtztYngtrpK1d4ivVGprYjvrpRGinYP2ETaX13UtseSz4pKnip/JbL+kCkuAxD3/UloK3v5p nfedotov@cisco.com
EOF

echo "apt_preserve_sources_list: true" | sudo tee /etc/cloud/cloud.cfg.d/99-local-mirror-only.cfg
sudo cp sources.list /etc/apt/
sudo apt-get update

wget https://raw.githubusercontent.com/pypa/pip/develop/contrib/get-pip.py
sudo python get-pip.py

# Install packages
sudo apt-get install -y openjdk-7-jre git python-dev libxml2-dev libxslt1-dev zlib1g-dev sshpass mysql-client libmysqlclient-dev gzip
sudo pip install ecdsa junitxml ncclient