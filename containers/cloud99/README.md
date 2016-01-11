#RUN Cloud99 container
CLOUD99_CONTAINER_ID=$(docker run -d -P --name cloud99 cloud99)
echo $(docker logs $CLOUD99_CONTAINER_ID | sed -n 1p)
docker port $CLOUD99_CONTAINER_ID 22


# install sshpass
# create cirros image for openstack with name ^cirros
cd /cloud99
. openrc
rally-manage db recreate
rally deployment create --fromenv --name=<deployment_name>
rally deployment check
. install.sh
python ha_engine/ha_main.py -f configs/keystone_api_executor.yaml