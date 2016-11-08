## Building container
* http://elk-docker.readthedocs.io/
* Run in this directory
```sh  
$ sudo docker build -t sqe/elk --no-cache --force-rm .
```
* This process will build the image.
* If you see the error like  
```sh
node validation exception
bootstrap checks failed
max virtual memory areas vm.max_map_count [65530] likely too low, increase to at least [262144]
```
* run
```sh
$  sudo sysctl -w vm.max_map_count=262144
```
* Finally run 
```sh
$  sudo docker run -p 7001:5601 -p 7002:9200 --name elk sqe/elk -it 
```
* Your kibana will be at http://<ip>:7001 (in container at 5601)
* ES at http://<ip>:7002/_search?pretty (in container at 9200)
* logstash beat is listening at 7003 (in container at 5044)
* In addition:
* logstash lamberjack listening at 7080
* /tmp/sqe.log is monitored 