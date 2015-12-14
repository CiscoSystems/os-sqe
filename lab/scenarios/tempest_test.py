import datetime
from fabric.api import local, cd


def start(context, log, args):
    test = args['test']
    etime = args['etime']
    tempest_path = args['tempest_path']

    start_time = datetime.datetime.now()
    with cd(tempest_path):
        while (datetime.datetime.now() - start_time).seconds < etime:
            local('source ~/VE/tempest/bin/activate && testr run {0}'.format(test))
