#!/bin/bash

WORK_DIR=`pwd`

cat >>/home/ubuntu/.ssh/authorized_keys <<EOF
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCj9HsmH5E2hlwOXpBd8FFQY0fxMBJBiFeAc/I9ds9WQMjeuLnYWICE2DCX7AoMSwPLl/IwKQZGV/Vt3nB12/EKvTMx6yCgfPOGrejzYYUhDSxJwuFg5KHDuLHXcUjDz/uAn2mzEDwPqtsxRSeKB/IYa7cn2VdgmrIi7PPc2/Gzk7CnYpqwMjMr1A9BxJz41yCN4gkNxk8LFxVtiAFQRuPVAU06yzEbQHPzPCZbVOpBo+TZcEOIepCy0DLrjcwEa26uBEeN13aGWaRuhtztYngtrpK1d4ivVGprYjvrpRGinYP2ETaX13UtseSz4pKnip/JbL+kCkuAxD3/UloK3v5p nfedotov@cisco.com
EOF

echo "apt_preserve_sources_list: true" | sudo tee /etc/cloud/cloud.cfg.d/99-local-mirror-only.cfg
sudo cp sources.list /etc/apt/
sudo apt-get update

sudo apt-get install -y openjdk-6-jre git python-pip python-dev
sudo pip install ecdsa junitxml