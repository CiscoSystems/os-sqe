from fabric.api import task

@task
def test():
    from fabric.api import run, settings, hide
    key = 'AAAAB3NzaC1yc2EAAAADAQABAAABAQC0gQ0i4KDVlcvncoDY+v0oQnXpmI7vhiDevgCbFM/S3DO2vsAulyl3PZ0kcjCakbpuTw3ugaKj2zlFu6Aqt8Z9YKr7juyld/lAbrl23LUVkiU/gNb1I6fGQb6rURl3sqv+8T5CUoA+SvdBw+d755bOzxlEloPGqc8H6oUp7Sr/l0BvNM5bZdCOCFtmR5ysaiQ6TiXMJKJWWFhdb15NYkAe1HmL7ca2j/oFNrSJzFQtuQmDnJNP9s7Kr/0K3JjyTeSsskoj3vu4uXOOAttLtU6ibugz21QN6/eek2KtWBfAqvZdIPWEefNV9DwtnaDqzyw8oFStWxqsf/5f2GdU9pH/'
    env = {'host_string': 'root@10.23.221.142', 'password': 'cisco123',
            'disable_known_hosts': True,
            'abort_on_prompts': True,
            'connection_attempts': 1,
            'warn_only': True}
    with settings(hide('warnings', 'stderr'), host_string='aaa', hosts=['10.23.221.142'], user='root', password='cisco123', warn_only=True, output_prefix='aa'):
        ans = run('ssh -o StrictHostKeyChecking=no comp1 "lspci | grep 710" # g7-2-vts comp1: sshpass -p cisco123 ssh root@10.23.221.142 ssh comp1')
        print 'ANS=', ans