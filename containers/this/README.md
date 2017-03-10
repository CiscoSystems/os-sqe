
## Building container
* Run in this directory
```sh  
$ docker build -t os-sqe --no-cache --force-rm .
```
* This process will build the image with os-sqe repo cloned and virtual env build in ~/venv.
* Finally run
```sh
$  docker run --name os-sqe os-sqe -it -v ${PWD}:/root/os-sqe
```
from base dir of repo
* os-sqe repo will be in ~/os-sqe
* virtual env will be in ~/venv
* .bashrc will initialize ~/venv
