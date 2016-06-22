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
            ip_mask_part = '--ip-address={} --netmask={} --static 1'.format(ip, mask) if not nic.is_pxe() and validators.ipv4(str(ip)) else ''
            mac = nic.get_mac()
            name = nic.get_name()
            if nic.is_ssh():
                gateway = nic.get_net()[1]
            if nic.is_bond():
                bond_mode = '802.3ad' if nic.is_ssh() else 'balance-xor'
                for name_slave, mac_port in nic.get_slave_nics().items():
                    mac = mac_port['mac']
                    network_commands.append('--interface={} --mac={} --interface-type=bond_slave --interface-master={}'.format(name_slave, mac, name))
                network_commands.append('--interface={} --interface-type=bond --bonding-opts="lacp_rate=1,miimon=50,xmit_hash_policy=1,updelay=0,downdelay=0,mode={}" {}'.format(name, bond_mode, ip_mask_part))
            else:
                network_commands.append('--interface={} --mac={} {}'.format(name, mac, ip_mask_part))

        systems = self.run('cobbler system list')
        if system_name in systems:
            self.run('cobbler system remove --name={}'.format(system_name))

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
        from lab.fi import FiServer
        from lab.cimc import CimcServer

        ks_meta = 'ProvTime={}-by-{}'.format(time_as_string(), getpass.getuser())

        nodes_to_deploy_by_cobbler = []
        for node in self.lab().get_nodes_by_class(FiServer) + self.lab().get_nodes_by_class(CimcServer):
            if filter(lambda x: x.is_pxe(), node.get_nics().values()):
                nodes_to_deploy_by_cobbler.append(node)

        nodes_to_check = []
        for node in nodes_to_deploy_by_cobbler:
            if node.is_nics_correct():
                continue
            nodes_to_check.append(node)
            system_name = self.cobbler_configure_for(node=node)
            node.cimc_configure()
            if self.lab().get_type() == self.lab().LAB_MERCURY:
                self.run('cobbler system edit --name {} --netboot-enabled=True --ksmeta="{}"'.format(system_name, ks_meta))
                node.cimc_power(node.POWER_CYCLE)

        for node in nodes_to_check:
            when_provided = node.run(command='cat ProvTime')
            if when_provided != ks_meta:
                raise RuntimeError('Wrong provisioning attempt- timestamps are not matched')
            node.actuate_hostname()

        return nodes_to_deploy_by_cobbler
