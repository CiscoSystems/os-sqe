def start(lab, log, args):
    """ This scenario is a pythonized version of bash script by Vel Kumar used to create the baseline topo for SRIOV bandwidth measurement
    """
    from lab.nodes.lab_server import LabServer

    cloud = lab.cloud

    cloud.os_cleanup()
    cloud.os_create_image(name='sriov', url='http://172.29.173.233/ucsm/CentOS-6-x86_64-GenericCloud-20140929_01_Cisco_enic_Login-root_Password-ubuntu.qcow2')
    cloud.create_key_pair()
    internal_nets = cloud.create_net_subnet(common_part_of_name='internal', class_a=1, how_many=2)
    provider_nets = cloud.create_net_subnet(common_part_of_name='provider', class_a=41, how_many=2, vlan=3040)
    di_internal_net = cloud.create_net_subnet(common_part_of_name='di-internal', class_a=11, how_many=1)
    service_nets = cloud.create_net_subnet(common_part_of_name='service', class_a=21, how_many=10)

    cloud.create_router(number=1, on_nets=internal_nets)

    instances = ['cf-sriov-ins-1',  'sf-sriov-ins-1', 'cf-sriov-ins-11', 'sf-sriov-ins-12']
    fips = cloud.create_fips(how_many=len(instances))

    for i, instance in enumerate(instances):
        ports = []

        ports.extend(cloud.create_ports(instance_name=instance, on_nets=internal_nets, sriov=False))
        ports.extend(cloud.create_ports(instance_name=instance, on_nets=di_internal_net, sriov=True))

        if instance.endswith('-1'):
            ports.extend(cloud.create_ports(instance_name=instance, on_nets=service_nets, sriov=True))
        else:
            ports.extend(cloud.create_ports(instance_name=instance, on_nets=internal_nets[:2], sriov=False))
            ports.extend(cloud.create_ports(instance_name=instance, on_nets=provider_nets, sriov=True))

        instance_name = cloud.create_instance(name=instance, flavor='m1.medium', image='sriov', on_ports=ports)

        cloud.os_cmd('nova floating-ip-associate {instance_name} {fip}'.format(instance_name=instance_name, fip=fips[i]))

        cloud.os_cmd('ping -c5 {fip}'.format(fip=fips[i]))
        instances[i] = LabServer(ip=fips[i], username='root', lab=None, name='a')

    # export http_proxy=http://proxy-wsa.esl.cisco.com:80/ && export https_proxy=http://proxy-wsa.esl.cisco.com:80/ && yum -y install epel-release && yum -y  update && yum -y install iperf
    # service iptables stop && chkconfig iptables off
    # iperf -s -p {port_num}
    # iperf -c {ip_of_server} -p {port_num} -M {mtu}
    # lspci -nn | grep 0071
    # grep ^pci_passthrough_whitelist nova.conf
    # grep iommu /etc/default/grub