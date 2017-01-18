from lab.nodes.lab_server import LabServer


class CobblerServer(LabServer):
    ROLE = 'cobbler'

    def cmd(self, cmd):
        return self.exe(command=cmd, is_warn_only=True)

    def cobbler_configure_for(self, node):
        import validators
        from lab.time_func import time_as_string

        self.log('{}: (Re)creating cobbler profile for {}'.format(self, node))

        system_name = '{}-{}'.format(self.lab(), node.get_id())
        comment = 'This system is created by {0} for LAB {1} at {2}'.format(__file__, self.lab(), time_as_string())

        network_commands = []
        gateway = None
        for master_name, nic in node.get_nics().items():
            ip, mask = nic.get_ip_and_mask()
            ip_mask_part = '--ip-address={} --netmask={} --static 1'.format(ip, mask) if not nic.is_pxe() and validators.ipv4(str(ip)) else ''
            macs = nic.get_macs()
            names = nic.get_names()
            if nic.is_ssh():
                gateway = nic.get_net().get_gw()
            if len(names) > 1:
                bond_mode = 'mode=802.3ad lacp_rate=1' if nic.is_ssh() else 'mode=balance-xor'
                for slv_name, slv_mac in zip(names, macs):
                    network_commands.append('--interface={} --mac={} --interface-type=bond_slave --interface-master={}'.format(slv_name, slv_mac, master_name))
                network_commands.append('--interface={} --interface-type=bond --bonding-opts="{} miimon=50 xmit_hash_policy=1 updelay=0 downdelay=0 " {}'.format(master_name, bond_mode, ip_mask_part))
            else:
                network_commands.append('--interface={} --mac={} {}'.format(master_name, macs[0], ip_mask_part))

        ans = self.cmd('cobbler system list | grep {}'.format(system_name))
        if system_name in ans:
            self.cmd('cobbler system remove --name={}'.format(system_name))

        self.cmd('cobbler system add --name={} --profile=RHEL7.2-x86_64 --kickstart=/var/lib/cobbler/kickstarts/sqe --comment="{}"'.format(system_name, comment))

        self.cmd('cobbler system edit --name={} --hostname={} --gateway={}'.format(system_name, node.get_hostname(), gateway))

        for cmd in network_commands:
            self.cmd('cobbler system edit --name={} {}'.format(system_name, cmd))

        ipmi_ip, ipmi_username, ipmi_password = node.get_oob()
        self.cmd('cobbler system edit --name={} --power-type=ipmilan --power-address={} --power-user={} --power-pass={}'.format(system_name, ipmi_ip, ipmi_username, ipmi_password))

        return system_name

    def cobbler_deploy(self):
        import getpass
        from lab.time_func import time_as_string
        from lab.nodes.fi import FiServer
        from lab.cimc import CimcServer

        ks_meta = 'ProvTime={}-by-{}'.format(time_as_string(), getpass.getuser())

        nodes_to_deploy_by_cobbler = []
        for node in self.lab().get_nodes_by_class(FiServer) + self.lab().get_nodes_by_class(CimcServer):
            if filter(lambda x: x.is_pxe(), node.get_nics().values()):
                nodes_to_deploy_by_cobbler.append(node)

        self.log(message='provisioning {}'.format(nodes_to_deploy_by_cobbler))

        nodes_to_check = []
        for node in nodes_to_deploy_by_cobbler:
            if node.r_is_nics_correct():
                continue
            nodes_to_check.append(node)
            system_name = self.cobbler_configure_for(node=node)
            node.cimc_configure()
            self.cmd('cobbler system edit --name {} --netboot-enabled=True --ksmeta="{}"'.format(system_name, ks_meta))
            node.cimc_power_cycle()

        for node in nodes_to_check:
            self.log('Waiting when server is online...')
            when_provided = node.exe(command='cat ProvTime')
            if 'ProvTime=' + when_provided != ks_meta:
                raise RuntimeError('Wrong provisioning attempt- timestamps are not matched')
            node.actuate_hostname()
            node.exe('mkdir -p cobbler && mv *.ks *.log *.cfg ProvTime cobbler')

        return nodes_to_deploy_by_cobbler
