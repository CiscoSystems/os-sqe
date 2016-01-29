def start(context, log, args):

    director = context.director()
    director.check_or_install_packages('java')
    director.run('mkdir /opt/ws')
    director.wget_file('http://172.29.173.233/nightly/osp7/haproxy.conf', '/opt/ws/')
    director.wget_file('http://172.29.173.233/nightly/osp7/logstash-2.1.1.tar.gz', '/opt/ws/')
    director.run('tar -xvf logstash-2.1.1.tar.gz', in_directory='/opt/ws/')
    haproxy_port_ip = context.controllers()[0].run(' ss -ntlp | grep 1993 | awk "\{print $4\}"')
    director.run('sed  s/HAPROXY_IP_PORT/{0}/g haproxy.conf'.format(haproxy_port_ip), in_directory='/opt/ws/')
    director.run('./logstash-2.1.1/bin/logstash -f haproxy.conf', in_directory='/opt/ws/')
