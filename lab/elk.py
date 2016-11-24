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

    def filter_error_warning_in_last_seconds(self, seconds):
        import json
        import math

        a = '''curl -XPOST 'localhost:9200/_search?pretty' -d '
            {
              "query": {  "filtered": {
                  "query": {"bool": { "should": [{ "match": { "loglevel": "ERROR"}},{ "match": { "loglevel": "WARNING" }}]}},
                  "filter": {"range": { "received_at": { "gte": "now-XXXXXs", "lte": "now"}}}
              }},
              "size": 10000
            }'
            '''
        a = a.replace('XXXXX', str(int(math.ceil(seconds))))
        r = self.exe(a)
        r = json.loads(r)
        return r

    def nodes(self):
        self.exe("curl --silent 'localhost:9200/_cat/nodes?v'")

    def version(self):
        self.exe("curl --silent 'localhost:9200'")
