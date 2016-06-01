def start(lab, log, args):
    """ This scenario is a parametrised scenario to do a number of tests dedicated to VTS
    """
    from lab.server import Server

    cloud = lab.cloud

    cloud.cleanup()

    n_instances = args['how-many-servers']
    n_nets = args['how-many-networks']

    image_name = cloud.create_image(name='vts-image', url='http://172.29.173.233/fedora/fedora-dnsmasq-localadmin-ubuntu.qcow2')
    cloud.create_key_pair()
    internal_nets = cloud.create_net_subnet(common_part_of_name='internal', class_a=10, how_many=n_nets, is_dhcp=False)

    for i in range(1, n_instances):
        port_pids = cloud.create_ports(instance_name=str(i), on_nets=internal_nets, is_fixed_ip=True)
        instance_name = cloud.create_instance(name=str(i), flavor='m1.medium', image=image_name, on_ports=port_pids)

        # cloud.cmd('ping -c5 {fip}'.format(fip=fips[i]))
        # instances[i] = Server(ip=fips[i], username='root', lab=None, name='a')

    # export http_proxy=http://proxy-wsa.esl.cisco.com:80/ && export https_proxy=http://proxy-wsa.esl.cisco.com:80/ && yum -y install epel-release && yum -y  update && yum -y install iperf
    # service iptables stop && chkconfig iptables off
    # iperf -s -p {port_num}
    # iperf -c {ip_of_server} -p {port_num} -M {mtu}
    # lspci -nn | grep 0071
    # grep ^pci_passthrough_whitelist nova.conf
    # grep iommu /etc/default/grub