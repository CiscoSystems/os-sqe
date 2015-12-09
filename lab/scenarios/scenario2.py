import datetime
import time
from fabric.api import local, cd
from multiprocessing import Pool


def testr_run(args):
    test = args[0]
    delay = args[1]
    etime = args[2]
    tempest_path = args[3]
    start_time = datetime.datetime.now()
    res = list()
    time.sleep(delay)
    with cd(tempest_path):
        if etime:
            while (datetime.datetime.now() - start_time).seconds < etime:
                res.append(local('source ~/VE/tempest/bin/activate && testr run {0}'.format(test), capture=True))
        else:
            return local('source ~/VE/tempest/bin/activate && testr run {0}'.format(test), capture=True)
    return res


def main(context, log, args):
    test = args['test']
    processes = args['processes']
    etime = args['etime']
    tempest_path = args['tempest_path']

    # Figure out execution time of a one test
    start_time = datetime.datetime.now()
    testr_run((test, 0, 0, tempest_path))
    execution_time = (datetime.datetime.now() - start_time).seconds
    print 'Single test takes {0} seconds'.format(execution_time)

    # Wait for 'delay' time before starting another test
    delay = execution_time / processes
    pool = Pool(processes=processes)
    args = [(test, delay * i, etime, tempest_path) for i in range(0, processes)]
    print 'Scenario {0}'.format(args)
    print pool.map(testr_run, args)

