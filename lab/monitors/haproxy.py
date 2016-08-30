def start(context, log, args):

    director = context.director()
    director.check_or_install_packages('java')
    director.exe('mkdir /opt/ws')
    director.wget_file('http://172.29.173.233/nightly/osp7/haproxy.conf', '/opt/ws/')
    director.wget_file('http://172.29.173.233/nightly/osp7/logstash-2.1.1.tar.gz', '/opt/ws/')
    director.exe('tar -xvf logstash-2.1.1.tar.gz', in_directory='/opt/ws/')
    haproxy_port_ip = context.controllers()[0].exe(' ss -ntlp | grep 1993 | awk "\{print $4\}"')
    director.exe('sed  s/HAPROXY_IP_PORT/{0}/g haproxy.conf'.format(haproxy_port_ip), in_directory='/opt/ws/')
    director.exe('./logstash-2.1.1/bin/logstash -f haproxy.conf', in_directory='/opt/ws/')
