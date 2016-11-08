FROM sebp/elk
MAINTAINER Kirill Shileev <kshileev@cisco.com>

RUN rm  /etc/logstash/conf.d/* && mkdir -p /etc/logstash/ssl/private && mkdir -p /etc/logstash/ssl/certs
COPY logstash.conf /etc/logstash/conf.d/logstash.conf
COPY elasticsearch-template-vmtp.json /etc/logstash/elasticsearch-template-vmtp.json
COPY openssl.cnf /etc/logstash/ssl/openssl.cnf
RUN openssl req -config "/etc/logstash/ssl/openssl.cnf" -x509 -subj '/C=US/ST=California/L=San Jose/0=Cisco Systems/CN=127.0.0.1' -days 3650 -batch -nodes -newkey rsa:2048 -keyout "/etc/logstash/ssl/private/logstash-forwarder.key" -out "/etc/logstash/ssl/certs/logstash-forwarder.crt"
