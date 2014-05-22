#!/bin/bash
# Command line parameters:
#	$1	openrc path
#	$2	config.sh of a virtual machines
#	$3	path of a cirros disk image
#   $4  tempest path


# Functions below were borrowed from devstack source
# Grab a numbered field from python prettytable output
# Fields are numbered starting with 1
# Reverse syntax is supported: -1 is the last field, -2 is second to last, etc.
# get_field field-number
function get_field {
    while read data; do
        if [ "$1" -lt 0 ]; then
            field="(\$(NF$1))"
        else
            field="\$$(($1 + 1))"
        fi
        echo "$data" | awk -F'[ \t]*\\|[ \t]*' "{print $field}"
    done
}

# Set an option in an INI file
# iniset config-file section option value
function iniset {
    local xtrace=$(set +o | grep xtrace)
    set +o xtrace
    local file=$1
    local section=$2
    local option=$3
    local value=$4

    [[ -z $section || -z $option ]] && return

    local sep=$(echo -ne "\x01")
    sed -i -e '/^\['${section}'\]/,/^\[.*\]/ s'${sep}'^\('${option}'[ \t]*=[ \t]*\).*$'${sep}'\1'"${value}"${sep} "$file"
    $xtrace
}

# *******************************************************************************
# Clone tempest, create/configyre virtualenv
# *******************************************************************************

dir=$(dirname $0)

tempest_path=$4
tempest_conf=${tempest_path}/etc/tempest.conf

git clone https://github.com/openstack/tempest.git

apt-get install -y python-dev
# lxml dependencies
apt-get install -y libxml2-dev libxslt1-dev
# cryptography dependencies
apt-get install -y build-essential libssl-dev libffi-dev

# Set up python virtual environment
python ${tempest_path}/tools/install_venv.py
source ${tempest_path}/.venv/bin/activate

# Install nosetests
pip install nose

# *******************************************************************************
# Prepare OpenStack
# *******************************************************************************

# Source openrc file
source $1
# Source config.sh
source $2

controller_ip=$(env | grep "OS_AUTH_URL" | grep -P -o "([0-9]{1,3}[\.]){3}[0-9]{1,3}")

# Create images in a glance
image_id=$(glance image-create --name=cirros-img --is-public=true --container-format=bare --disk-format=qcow2 < $3 | grep ' id ' | get_field 2)
alt_image_id=$(glance image-create --name=cirros-img_alt --is-public=true --container-format=bare --disk-format=qcow2 < $3 | grep ' id ' | get_field 2)

# Create 'demo' tenant and user
tenant_demo_id=$(keystone tenant-create --name demo | grep ' id ' | get_field 2)
keystone user-create --name=demo --pass=secret --tenant-id=$tenant_demo_id --email=demo@domain.com
# Create 'alt_demo' tenant and user
tenant_alt_demo_id=$(keystone tenant-create --name alt_demo | grep ' id ' | get_field 2)
keystone user-create --name=alt_demo --pass=secret --tenant-id=$tenant_alt_demo_id --email=alt_demo@domain.com

# Create public network
public_net_id=$(neutron net-create public --router:external=True | grep ' id ' | get_field 2)
neutron subnet-create --allocation-pool start="${NET_EXTERNAL}.2",end="${NET_EXTERNAL}.254" public "${NET_EXTERNAL}.0/24"
# Create private network
neutron net-create fixed --shared
fixed_subnet_id=$(neutron subnet-create fixed 192.168.100.0/24 --dns_nameservers list=true "${NET_EXTERNAL}.1" | grep ' id ' | get_field 2)
# Create router. Add interface and set gateway
public_router_id=$(neutron router-create router1 | grep ' id ' | get_field 2)
neutron router-interface-add router1 $fixed_subnet_id
neutron router-gateway-set router1 $public_net_id

# *******************************************************************************
# Configure tempest
# *******************************************************************************

scenario_img_dir=${tempest_path}/images

cp ${dir}/tempest.conf ${tempest_conf}
iniset $tempest_conf compute image_ref $image_id
iniset $tempest_conf compute image_ref_alt $alt_image_id
iniset $tempest_conf network public_network_id $public_net_id
iniset $tempest_conf network public_router_id $public_router_id
iniset $tempest_conf dashboard dashboard_url "http://${controller_ip}/"
iniset $tempest_conf dashboard login_url "http://${controller_ip}/horizon/auth/login/"
iniset $tempest_conf identity uri "http://${controller_ip}:5000/v2.0/"
iniset $tempest_conf identity uri_v3 "http://${controller_ip}:5000/v3/"
iniset $tempest_conf scenario img_dir $scenario_img_dir

# Download images for [scenario] tempest tests
mkdir $scenario_img_dir
cd $scenario_img_dir
wget http://download.cirros-cloud.net/0.3.2/cirros-0.3.2-x86_64-uec.tar.gz
tar -xvf cirros-0.3.2-x86_64-uec.tar.gz

deactivate
