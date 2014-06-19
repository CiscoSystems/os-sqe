#!/bin/bash
#cd /root/
source ./openrc
rm -rf prepare_for_tempest_dir
echo "deleting cirros-0.3.1-x86_64-disk.img ...."
rm ./cirros-*img
echo "deleting all glance images ....."
glance image-list | grep qcow2 | awk {'print $2'} | xargs glance image-delete
echo "deleting precise-server-cloudimg-amd64-disk1.img ...."
rm ./precise-server-cloudimg-amd64-disk1.img
echo "deleting all tenants with demo ...."
#keystone tenant-list | grep "demo" | awk {'print $2'} | xargs keystone tenant-delete
keystone tenant-delete demo
keystone tenant-delete alt_demo
echo "deleting all users demo ...."
keystone user-delete demo
keystone user-delete alt_demo
echo "clearing floating IPs from routers ...."
for ip in $(neutron floatingip-list | grep -E "192.168|10.10" | awk {'print $2'}); do neutron floatingip-delete $ip; done
echo "clearing gateway from routers ...."
neutron router-list | grep " router1 " | awk {'print $2'} | xargs neutron router-gateway-clear
pslist=$(neutron port-list | grep subnet | awk {'print $2'})
routerlist=$(neutron router-list | grep " router1 " | awk {'print $2'})
for i in $routerlist; do 
    for j in $pslist; do
        echo "deleting interface $j in router $i ...."
        neutron router-interface-delete $i port=$j;
        neutron port-delete $j; 
    done
done
echo "deleting routers ...."
for i in $routerlist; do neutron router-delete $i; done
echo "deleting networks ...."
for i in $(neutron net-list | grep -E "public|net10" |  awk {'print $2'}); do neutron net-delete $i; done
echo "deleting subnets ...."
for i in $(neutron subnet-list | grep start | awk {'print $2'}); do neutron subnet-delete $i; done
echo "deleting cirros from tmp ...."
cd /tmp
rm -rf cirros-0.3.1-x86_64-uec*
