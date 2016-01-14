from fabric.api import task


@task
def run_elk():
    """ Deploy elk stack as container """
    from fabric.api import sudo

    sudo('docker pull sebp/elk')
    sudo('docker run -p 7777:5601 -p 9999:9200 -p 7744:5044 -p 7700:5000 -it --name elk sebp/elk')


@task
def json_to_es():
    """Push json.log to our ES and index it """
    from lab.server import Server

    with open('json.log') as f:
        log = f.read()

    with open('elk', 'w') as f:
        f.write('{ "index" : { "_index" : "sqe", "_type" : "type1", "_id" : "1" } }\n')

    with open('elk', 'a') as f:
        f.write(log)
    Server.run_local('curl -s -XPOST 172.29.173.236:9999/_bulk --data-binary @elk')


@task
def kill_index(index):
    """Kill given index in ES
    :param index: name of index to delete
    """
    from lab.server import Server

    Server.run_local('curl -s -XDELETE 172.29.173.236:9999/{index}'.format(index=index))
