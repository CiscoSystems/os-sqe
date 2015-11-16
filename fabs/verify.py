from fabric.api import task, settings, run, get, cd


@task
def os_logs(cloud_entry_point=''):
    log_dirs = ['/var/log/neutron']

    for log_dir in log_dirs:
        with cd(log_dir):
            tmp_file = '/tmp/{0}_logs.tgz'.format(log_dir.split('/')[-1])
            run('tar czvf {0} *.log'.format(tmp_file))
            get(remote_path=tmp_file, local_path='.')


@task
def os_rpm_version(ip='172.29.173.73', user='root', password='cisco123'):
    """Returns the rpm version of OSP installed"""
    with settings(host_string='{user}@{ip}'.format(user=user, ip=ip), password=password):
        ans = run('rpm -qa | grep cisco')
        print ans


def nodes_of_cloud(cloud_entry_point='172.29.173.73'):
    pass
