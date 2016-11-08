from fabric.api import task


@task
def json_to_es():
    """fab elk.json_to_es \t\t\t\t Push json.log to our ES and index it."""
    from lab.server import Server

    with open('json.log') as l:
        with open('elk', 'w') as e:
            for line in l:
                e.write('{ "index" : { "_index" : "sqe", "_type" : "type1"} }\n')
                e.write(line)
    server = Server(ip='localhost', username=None, password=None)
    server.exe('curl -s -XPOST 172.29.173.236:9999/_bulk --data-binary @elk')


@task
def kill_index(index):
    """fab elk.kill_index:index_name \t\t Kill given index in ES.
        :param index: name of index to delete
    """
    from lab.server import Server

    server = Server(ip='localhost', username=None, password=None)
    server.exe('curl -s -XDELETE 172.29.173.236:9999/{index}'.format(index=index))
