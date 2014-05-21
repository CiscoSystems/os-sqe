## Overview
The scripts allow to spin up virtual machines with predefined machines parameters, network parameters and 'init paremeters'. 

Machines and network parameters should be specified in config.sh file. 

## Machines parameters
Below a list of parameters related to machines configuration
- *NAME* used as a prefix in virtual machines names.
- *CONTROL_SERVERS*/*COMPUTE_SERVERS* amount of a control / compute virtual machines that will be created
- *BUILD_SERVER_RAM* RAM size of a build server in Gb
- *CONTROL_SERVER_RAM* RAM size of a control servers in Gb
- *COMPUTE_SERVER_RAM* RAM size of a compute servers in Gb
- *BUILD_SERVER_DISK_SIZE* disk size of a build server in Gb
- *CONTROL_SERVER_DISK_SIZE* disk size of a control server in Gb
- *COMPUTE_SERVER_DISK_SIZE* disk size of a compute server in Gb
- *COMPUTE_SERVER_CPU* cpu amount of each compute server

## Network configuration

There are 5 virtual networks configured.
- *boot network* DHCP enabled network, NAT enabled, global traffic is forwarded to default gateway of a host machine
- *admin* private network
- *public* private network
- *internal* private network
- *external* NAT enabled netwwork, DHCP is disabled

Each virtual machine is connected to certain amount network. Here is a map server VS network name:
- *Build server* boot, admin
- *controller server* boot, admin, public, internal, external
- *compute server* boot, admin, public, internal, external

Networks addresses could be specified in config.sh file. It is assumed all networks have CIDR=/24. Thus you should specify only first three octets of a network ip address.
- *NET_BOOT* address of a boot network
- *NET_ADMIN* address of a admin network
- *NET_PUBLIC* address of a public network
- *NET_INTERNAL* address of a internal network
- *NET_EXTERNAL* address of a external network

#### Note
Admin network has a DNS record about build server ip address: *${NET_ADMIN}.2*, and a hostname is *build-server* *build-server.domain.name*. Nevertheless interfaces configuration should be configured manually for each virtual machines. Keep in mind ip of build server.

IP address of a VM in a boot network is assigned by DHCP server. The value could be found in output of a create.sh.

## Boot image
The script uses cloud image (tested against ubuntu) to boot virtual machines. Fullpath of an image chould be specified in *IMG_FULLPATH* parameter in *config.sh* file. The image is used for creating VMs, thus you remove it once create.sh stops working.

## Machines initialization
Ubuntu cloud images has cloud-init tool preinstalled. It helps user to configure a VM once it boots first time. Parameters for cloud-init are stored in *user-data.yaml* file. It is already filled with *localadmin* user and *git* *pip* packages. You may add whatever you want (see http://cloudinit.readthedocs.org/en/latest/topics/examples.html). The *user-data.yaml* file is used for all virtual machines.

Also by default a ssh public key is added to the localadmin's ssh authorized keys file. Private id_rsa is in repository. So you may ssh to vm using this id_rsa (ssh -i id_rsa localadmin@<ip>). You would have to change permissions of the id_rsa to 600 (chmod 600 id_rsa) otherwise you face "Permissions 0XXX for 'id_rsa' are too open." error.

## Using
There re two bash scripts
- *create.sh* it creates virtual machines but it does not start them (use *virsh start <machines name>*). It also creates networks and starts them.
- *undefine.sh* it destroys/undefined virtual machines and networks.
Both scripts use parameters in config.sh. So in order to undefine machines you need to provide same config.sh that was used by create.sh
