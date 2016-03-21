FROM ubuntu:14.04
MAINTAINER Kirill Shileev <kshileev@cisco.com>

RUN apt-get update
RUN apt-get install -y git python-setuptools python-dev libffi-dev libssl-dev

RUN git clone -b proposed  https://github.com/cisco-openstack/tempest.git

COPY openrc /tempest/etc/openrc

RUN easy_install pip
RUN pip install -r /tempest/requirements.txt
RUN pip install -r /tempest/test-requirements.txt

RUN cp /tempest/etc/accounts.yaml.sample  /tempest/etc/accounts.yaml
RUN cd /tempest && python tools/config_tempest.py --create identity.uri $(grep URL /tempest/etc/openrc | cut -f2 -d '=') identity.admin_password $(grep PASSWORD /tempest/etc/openrc | cut -f2 -d '=')

RUN cd /tempest && ostestr --regex  '(?!.*\[.*\bslow\b.*\])(^tempest\.(api|scenario))' > results.log