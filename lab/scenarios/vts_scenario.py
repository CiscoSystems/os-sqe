from lab.worker import Worker


class VtsScenario(Worker):
    # noinspection PyAttributeOutsideInit
    def setup(self):
        self._n_instances = self._kwargs['how-many-servers']
        self._n_nets = self._kwargs['how-many-networks']

    def loop(self):
        self._cloud.os_cleanup()

        image_name = self._cloud.os_create_image(name='vts-image', url='http://172.29.173.233/fedora/fedora-dnsmasq-localadmin-ubuntu.qcow2')
        self._cloud.create_key_pair()
        internal_nets = self._cloud.create_net_subnet(common_part_of_name='internal', class_a=10, how_many=self._n_nets, is_dhcp=False)

        for i in range(1, self._n_instances + 1):
            port_pids = self._cloud.create_ports(instance_name=str(i), on_nets=internal_nets, is_fixed_ip=True)
            instance_name = self._cloud.create_instance(name=str(i), flavor='m1.medium', image=image_name, on_ports=port_pids)
            self._log.info('instance={0} created'.format(instance_name))
            # cloud.cmd('ping -c5 {fip}'.format(fip=fips[i]))
            # instances[i] = Server(ip=fips[i], username='root', lab=None, name='a')

        # export http_proxy=http://proxy-wsa.esl.cisco.com:80/ && export https_proxy=http://proxy-wsa.esl.cisco.com:80/ && yum -y install epel-release && yum -y  update && yum -y install iperf
        # service iptables stop && chkconfig iptables off
        # iperf -s -p {port_num}
        # iperf -c {ip_of_server} -p {port_num} -M {mtu}
        # lspci -nn | grep 0071
        # grep ^pci_passthrough_whitelist nova.conf
        # grep iommu /etc/default/grub