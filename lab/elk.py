class Elk(object):
    def __init__(self, proxy):
        self._proxy = proxy
    
    def exe(self, command):
        return self._proxy.exe(command)
        
    def health(self):
        self.exe("curl --silent 'localhost:9200/_cat/health?v'")

    def index_create(self):
    
        with self.open_artifact('json.log', mode='r') as l:
            with open('elk', 'w') as e:
                for n, line in enumerate(l, start=1):
                    e.write('{"index":{"_id":"{}"}}\n{}'.format(n, line))
        self.exe("curl --silent -XPOST 'localhost:9200/sqe/type1/_bulk?pretty&refresh' --data-binary @elk")

    def index_kill(self, index):
        return self.exe("curl --silent -XDELETE 'localhost:9200/{}'".format(index))

    def index_list(self):
        return self.exe("curl --silent 'localhost:9200/_cat/indices?v'")

    def index_mapping(self, index, field=None):
        return self.exe("curl -XGET 'http://localhost:9200/{}/_mapping{}?pretty'".format(index, '/field/' + field if field else ''))

    def search_all(self):
        return self.exe("curl --silent 'localhost:9200/_search?q=*&size=0&pretty'")

    def search_match(self, field, what):
        import json
    
        return json.loads(self.exe("curl --silent 'localhost:9200/_search?q=loglevel:ERROR&size=4&sort=logdate:asc&pretty'".format(field, what)))

    def filter_error_warning_date_range(self, start):
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
        r = json.loads(self.exe(a))
        for log in r['hits']['hits']:
            if 'logdate' not in log['_source']:
                continue
            logdate = log['_source']['logdate']
            date = datetime.strptime(logdate[:19], '%Y-%m-%d %H:%M:%S')  # [:19] truncates milliseconds or AM PM
            if date > start:
                lab_logger.error(log['_source'])

    def filter_date_range(self, start):
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
        r = self.exe(a)
        r = json.loads(r)
        return r

    def nodes(self):
        self.exe("curl --silent 'localhost:9200/_cat/nodes?v'")

    def version(self):
        self.exe("curl --silent 'localhost:9200'")
