from fabric.api import task


@task
def run_elk():
    """fab elk.run_elk \t\t\t\t Deploy elk stack as docker container."""
    from fabric.api import sudo

    sudo('docker pull sebp/elk')
    sudo('docker run -p 7777:5601 -p 9999:9200 -p 7744:5044 -p 7700:5000 -it --name elk sebp/elk')


@task
def json_to_es():
    """fab elk.json_to_es \t\t\t\t Push json.log to our ES and index it."""
    from lab.server import Server

    with open('json.log') as l:
        with open('elk', 'w') as e:
            for line in l:
                e.write('{ "index" : { "_index" : "sqe", "_type" : "type1"} }\n')
                e.write(line)
    Server.run_local('curl -s -XPOST 172.29.173.236:9999/_bulk --data-binary @elk')


@task
def kill_index(index):
    """fab elk.kill_index:index_name \t\t Kill given index in ES.
        :param index: name of index to delete
    """
    from lab.server import Server

    Server.run_local('curl -s -XDELETE 172.29.173.236:9999/{index}'.format(index=index))
