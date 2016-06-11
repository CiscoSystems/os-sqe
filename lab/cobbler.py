from lab.server import Server


class CobblerServer(Server):
    def cmd(self, cmd):
        pass

    def __repr__(self):
        _, ssh_u, ssh_p = self.get_ssh()
        ip, oob_u, oob_p = self.get_oob()
        return u'{l} {n} | sshpass -p {p1} ssh {u1}@{ip} http://{ip}/cobbler_api with {u2}/{p2}'.format(l=self.lab(), n=self.get_id(), ip=ip, p1=ssh_p, u1=ssh_u, p2=oob_p, u2=oob_u)

    def cobbler_configure_for(self, node):
        import validators
        from lab.time_func import time_as_string
        from lab.logger import lab_logger

        lab_logger.info('{}: (Re)creating cobbler profile for {}'.format(self, node))

        system_name = '{}-{}'.format(self.lab(), node.get_id())
        comment = 'This system is created by {0} for LAB {1} at {2}'.format(__file__, self.lab(), time_as_string())

        network_commands = []
        gateway = None
        for nic in node.get_nics().values():
            ip, mask = nic.get_ip_and_mask()
            ip_mask_part = '--ip-address={} --netmask={}'.format(ip, mask) if validators.ipv4(str(ip)) else ''
            mac = nic.get_mac()
            name = nic.get_name()
            if nic.is_ssh():
                gateway = nic.get_net()[0]
            if nic.is_bond():
                for name_slave, mac in {name + '1': mac.replace('00:', '01:'), name + '2': mac.replace('00:', '02:')}.items():
                    network_commands.append('--interface={} --mac={} --interface-type=bond_slave --interface-master={}'.format(name_slave, mac, name))
                network_commands.append('--interface={} --interface-type=bond --bonding-opts="miimon=100 mode=1" {}'.format(name, ip_mask_part))
            else:
                network_commands.append('--interface={} --mac={} {}'.format(name, mac, ip_mask_part))

        systems = self.run('cobbler system list')
        if system_name not in systems:
            self.run('cobbler system add --name={} --profile=RHEL7.2-x86_64 --kickstart=/var/lib/cobbler/kickstarts/sqe --comment="{}"'.format(system_name, comment))

        self.run('cobbler system edit --name={} --hostname={} --gateway={}'.format(system_name, node.hostname(), gateway))

        for cmd in network_commands:
            self.run('cobbler system edit --name={} {}'.format(system_name, cmd))

        ipmi_ip, ipmi_username, ipmi_password = node.get_oob()
        self.run('cobbler system edit --name={} --power-type=ipmilan --power-address={} --power-user={} --power-pass={}'.format(system_name, ipmi_ip, ipmi_username, ipmi_password))

        return system_name

    def cobbler_deploy(self):
        import getpass
        from lab.time_func import time_as_string

        ks_meta = 'ProvTime={}-by-{}'.format(time_as_string(), getpass.getuser())

        nodes = filter(lambda x: x.is_deploy_by_cobbler(), self.lab().get_nodes_by_class())
        for node in nodes:
            system_name = self.cobbler_configure_for(node=node)
            if self.lab().get_type() == self.lab().LAB_MERCURY:
                self.run('cobbler system edit --name {} --netboot-enabled=True --ksmeta="{}"'.format(system_name, ks_meta))
                self.run('cobbler system reboot --name={}'.format(system_name))
