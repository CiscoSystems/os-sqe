import json
import netaddr
import unicodedata

from fabric.api import local


def _local(cmd, split=True):
    r = local(cmd, capture=True).stdout
    return r.split('\n') if split else r


def get_ovs_ports(ovs_bridge):
    ovs_ports_dict = {}
    for port_name in _local('sudo ovs-vsctl list-ports {0}'.format(ovs_bridge)):
        print '\nGetting info of port ', port_name
        _uuid = _local('sudo ovs-vsctl find port name={0}'.format(port_name))[0].split(':')[1].strip()
        vlan = _local('sudo ovs-vsctl get port {0} tag'.format(_uuid), split=False)
        if vlan != '[]':
            ovs_ports_dict[vlan] = {'_uuid': _uuid, 'name': port_name}
    return ovs_ports_dict


def get_ovs_bridges():
    bridges = local('sudo ovs-vsctl list-br', capture=True)
    return bridges.stdout.split('\n')


def get_vtc_host_connection_id(vtc_ui_client, device_name, device_port):
    host_inventory = vtc_ui_client.get_host_inventory(device_name)
    for h in host_inventory:
        if h['port_name'] == device_port:
            return h['connection_id']


def create_access_port(vtc_ui_client, network_id, device_name, device_port, ovs_bridge, binding_host_id):
    def to_ascci(str):
        return unicodedata.normalize('NFKD', str).encode('ascii', 'ignore')

    connection_id = get_vtc_host_connection_id(vtc_ui_client, device_name, device_port)
    if not connection_id:
        raise Exception('Could not fond interface {0} of {1}. Check hosts inventory'.format(device_port, device_name))

    net = vtc_ui_client.get_overlay_network(network_id)
    tenant = vtc_ui_client.get_tenant()
    ports = vtc_ui_client.get_overlay_network_ports(net['id'])

    # Create port
    data = {'resource': {
        'ToRPortToDelete': [to_ascci(p['id']) for p in ports],
        'id': to_ascci(net['id']),
        'network': {
            'network_name': to_ascci(net['name']),
            #'router-external': net['router-external']},
            'router-external': False},
        'tenant_id': to_ascci(tenant['vmm-tenant-id']),
        'tenant_name': to_ascci(tenant['name']),
        'tor_port': [
            {
                'binding_host_id': binding_host_id,
                'connid': [{'id': to_ascci(connection_id)}],
                'device_id': device_name,
                'mac': "",
                'tagging': 'mandatory',
                'type': "baremetal"
            }
        ]}
    }
    response = vtc_ui_client.put_network_port(net['id'], json.dumps(data))
    if not response.status_code == 200:
        raise Exception(response)

    ports = vtc_ui_client.get_overlay_network_ports(net['id'])
    created_ports = [p for p in ports if p['connid'] == connection_id]

    if len(created_ports) == 0:
        raise Exception('Access port does not exist')

    # Create OVS ports
    p = created_ports[0]
    vlan_number = str(p['vlan_number'])

    subnets = vtc_ui_client.get_overlay_network_subnets(net['id'])
    if len(subnets) == 0:
        raise Exception("There are no subnets. {0}".format(net))

    port_name = 'vlan{0}'.format(vlan_number)
    port_network = netaddr.IPNetwork(subnets[0]['cidr'])
    port_ip = port_network[254]
    local('sudo ovs-vsctl add-port {0} {1} -- set interface {1} type=internal'.format(ovs_bridge, port_name))
    local('sudo ovs-vsctl set port {0} tag={1}'.format(port_name, vlan_number))
    local('sudo ip address add {ip}/{cidr} dev {port_name}'.format(ip=port_ip, cidr=port_network.prefixlen, port_name=port_name))
    local('sudo ip link set dev {0} up'.format(port_name))


def delete_ports(vtc_ui_client, device_name, device_port, ovs_bridge):
    connection_id = get_vtc_host_connection_id(vtc_ui_client, device_name, device_port)
    if not connection_id:
        raise Exception('Could not fond interface {0} of {1}. Check hosts inventory'.format(device_port, device_name))

    ovs_ports_dict = get_ovs_ports(ovs_bridge)
    cur_networks = {net['id']: net for net in vtc_ui_client.get_overlay_networks()}
    for net_id, net in cur_networks.iteritems():
        cur_ports = vtc_ui_client.get_overlay_network_ports(net_id)
        created_ports = [p for p in cur_ports if p['connid'] == connection_id]
        for p in created_ports:
            vlan_number = str(p['vlan_number'])
            if vlan_number in ovs_ports_dict:
                local('sudo ovs-vsctl del-port {0} {1}'.format(ovs_bridge, ovs_ports_dict[vlan_number]['name']))
                vtc_ui_client.delete_network_port(p['id'])
