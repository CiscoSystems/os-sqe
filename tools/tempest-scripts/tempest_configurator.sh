#!/bin/bash
#cd /root/
source ./openrc
#wget http://download.cirros-cloud.net/0.3.2/cirros-0.3.2-x86_64-disk.img
#glance image-create --name=cirros-0.3-x86_64 --is-public=true --container-format=bare --disk-format=qcow2 < cirros-0.3.2-x86_64-disk.img
if [ -e ./external_net ]; then
EXTERNAL_NET=$(cat ./external_net)
else
EXTERNAL_NET="10.10.10"
fi
echo "Reinitialize the dir"
rm -rf prepare_for_tempest_dir
mkdir -p prepare_for_tempest_dir
cd prepare_for_tempest_dir/
echo "downloading cirros-0.3.2-x86_64-disk.img ...."
wget -nv http://172.29.173.233/cirros-0.3.2-x86_64-disk.img
#wget -nv http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-disk.img
glance image-create --name=cirros-0.3-x86_64 --is-public=true --container-format=bare --disk-format=qcow2 < ./cirros-0.3.2-x86_64-disk.img
#wget http://uec-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
#glance image-create --name=trusty-server --is-public=true --container-format=bare --disk-format=qcow2 < ./trusty-server-cloudimg-amd64-disk1.img
echo "downloading precise-server-cloudimg-amd64-disk1.img ...."
#wget -nv http://uec-images.ubuntu.com/server/precise/current/precise-server-cloudimg-amd64-disk1.img
#wget -nv http://172.29.173.233/precise-server-cloudimg-amd64-disk1.img
glance image-create --name=precise-server  --is-public=true --container-format=bare --disk-format=qcow2 < ./cirros-0.3.2-x86_64-disk.img
keystone tenant-create --name demo
kid1=$(keystone tenant-list | grep " demo " | awk {'print $2'})
keystone user-create --name=demo --pass=secret --tenant-id=$kid1 --email=demo@domain1.com
keystone tenant-create --name alt_demo
kid2=$(keystone tenant-list | grep " alt_demo " | awk {'print $2'})
keystone user-create --name=alt_demo --pass=secret --tenant-id=$kid2  --email=alt_demo@domain1.com
keystone tenant-create --name openstack
kid3=$(keystone tenant-list | grep " openstack " | awk {'print $2'})
keystone user-create --name=admin --pass=Cisco123 --tenant-id=$kid3 --email=admin@domain1.com
uid1=$(keystone user-list | grep " admin " | awk {'print $2'})
rid1=$(keystone role-list | grep " admin " |  awk {'print $2'})
keystone user-role-add --tenant-id=$kid3 --user-id=$uid1 --role-id=$rid1
keystone user-role-add --tenant-id=$kid1 --user-id=$uid1 --role-id=$rid1
neutron net-create public --router:external=True
neutron subnet-create --allocation-pool start=${EXTERNAL_NET}.2,end=${EXTERNAL_NET}.254 public ${EXTERNAL_NET}.0/24
neutron net-create net10 --shared
neutron subnet-create net10 192.168.1.0/24 --dns_nameservers list=true 8.8.8.8 8.8.4.4
neutron router-create router1
sid=$(neutron subnet-list | grep "192.168.1.0/24" |  awk {'print $2'})
neutron router-interface-add router1 $sid
nid=$(neutron net-list | grep " public " |  awk {'print $2'}) 
neutron router-gateway-set router1 $nid

cd /tmp
wget -nv http://download.cirros-cloud.net/0.3.1/cirros-0.3.2-x86_64-uec.tar.gz