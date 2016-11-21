from fabric.api import local


def health():
    local("curl --silent 'localhost:9200/_cat/health?v'")


def index_create(self):

    with self.open_artifact('json.log', mode='r') as l:
        with open('elk', 'w') as e:
            for n, line in enumerate(l, start=1):
                e.write('{"index":{"_id":"{}"}}\n{}'.format(n, line))
    local("curl --silent -XPOST 'localhost:9200/sqe/type1/_bulk?pretty&refresh' --data-binary @elk")


def index_kill(index):
    return local("curl --silent -XDELETE 'localhost:9200/{}'".format(index))


def index_list():
    return local("curl --silent 'localhost:9200/_cat/indices?v'", capture=True)


def index_mapping(index, field=None):
    return local("curl -XGET 'http://localhost:9200/{}/_mapping{}?pretty'".format(index, '/field/' + field if field else ''), capture=True)


def search_all():
    return local("curl --silent 'localhost:9200/_search?q=*&size=0&pretty'", capture=True)


def search_match(field, what):
    import json

    return json.loads(local("curl --silent 'localhost:9200/_search?q=loglevel:ERROR&size=4&sort=logdate:asc&pretty'".format(field, what), capture=True))


def filter_error_warning_date_range(start):
    import json
    from datetime import datetime
    from lab.logger import lab_logger

    a = '''
curl -XPOST 'localhost:9200/_search?pretty' -d '
{
  "query": {"bool": { "should": [{ "match": { "loglevel": "ERROR"}},{ "match": { "loglevel": "WARNING" }}]}},
  "size": 10000
}'
'''
    r = json.loads(local(a, capture=True))
    for log in r['hits']['hits']:
        if 'logdate' not in log['_source']:
            continue
        logdate = log['_source']['logdate']
        date = datetime.strptime(logdate[:19], '%Y-%m-%d %H:%M:%S')  # [:19] truncates milliseconds or AM PM
        if date > start:
            lab_logger.error(log['_source'])


def filter_date_range(start):
    import json

    a = '''
curl -XPOST 'localhost:9200/_search?pretty' -d '
{
  "query": {  "filtered": {
      "query": { "match_all": {}},
      "filter": {"range": { "recieved_at": { "gte": "2016-11-16T11:12:00", "lte": "now"}}}
  }},
  "size": 0
}'
'''
    a = a.replace('start_time', start.strftime('%Y-%m-%d %H:%M:%S'))
    r = local(a, capture=True)
    r = json.loads(r)
    pass


def nodes():
    local("curl --silent 'localhost:9200/_cat/nodes?v'")


def version():
    local("curl --silent 'localhost:9200'")
