FROM registry.access.redhat.com/rhel
MAINTAINER Dmitry Ratushnyy <dratushn@cisco.com>
COPY ./setup.sh /setup.sh
RUN /bin/bash setup.sh
COPY ./openrc /cloud99/openrc
COPY  ./configs /cloud99/configs
COPY  ./rally /cloud99/rally

EXPOSE 22
EXPOSE 8090
CMD [ "/usr/sbin/sshd", "-D"]
