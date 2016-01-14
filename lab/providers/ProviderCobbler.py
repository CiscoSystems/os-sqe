from lab.providers import Provider


class CobblerError(Exception):
    pass


class ProviderCobbler(Provider):
    """Creates servers via PXE boot from given cobbler selector.

    Cobbler selector may contain a combination of fields
    to select a number of system. It's user responsibility to provide selector
    which selects something. Since cobbler stores servers password encrypted
    the user needs to specify it configuration. All servers selected must have
    the same password.
    """
    def sample_config(self):
        return {'host': 'ip or FQDN of cobbler server',
                'user': 'username on cobbler server',
                'password': 'password on cobbler server',
                'system_password': 'password on all servers deployed by cobbler',
                'selector': {'name': 'cobbler_system_name', 'owners': 'user1'},
                'force_pxe_boot': 'set True if you want to force PXE re-provisioning'
                }

    def __init__(self, config):
        import datetime
        import xmlrpclib
        import os

        super(ProviderCobbler, self).__init__(config=config)
        self.host = config['host']
        self.user = config['user']
        self.password = config['password']
        self.selector = config['selector']
        self.system_password = config['system_password']
        self.force_pxe_boot = config['force_pxe_boot']
        self.__cobbler = xmlrpclib.Server(uri="http://{host}/cobbler_api".format(host=self.host))

        now = datetime.datetime.utcnow()
        self.prov_time = now.strftime('%b-%d-%H-%M-%S-UTC-by-{0}'.format(os.getenv('USER')))

    @staticmethod
    def is_valid_ipv4(ip):
        import socket

        if not ip:
            return False
        if ip.count('.') != 3:
            return False
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False

    @staticmethod
    def ip_for_system(rendered_system):
        for key, value in rendered_system.iteritems():
            if 'ip_address' in key and ProviderCobbler.is_valid_ipv4(ip=value):
                return value
        raise CobblerError('No valid ip address found for system "{0}". Check IP Address field in System/Networking'.format(rendered_system['name']))

    @staticmethod
    def username_for_system(rendered_system):
        if 'username' not in rendered_system['mgmt_parameters']:
            raise CobblerError('No system username defined for system "{0}". Check System/Management/Parameters'.format(rendered_system['name']))
        return rendered_system['mgmt_parameters']['username']

    def reboot_system(self, system_name):
        from lab.server import Server
        from lab.logger import lab_logger

        token = self.__cobbler.login(self.user, self.password)
        handle = self.__cobbler.get_system_handle(system_name, token)

        if self.force_pxe_boot:
            self.__cobbler.modify_system(handle, 'netboot_enabled', True, token)
            self.__cobbler.modify_system(handle, 'ks_meta', 'ProvTime={0}'.format(self.prov_time), token)
            self.__cobbler.modify_system(handle, 'comment', 'Used to deploy the director', token)
        self.__cobbler.power_system(handle, "reboot", token)
        rendered = self.__cobbler.get_system_as_rendered(system_name)

        server = Server(ip=self.ip_for_system(rendered),
                        username=self.username_for_system(rendered),
                        ssh_public_key=rendered.get("redhat_management_key"),
                        password=self.system_password,
                        ssh_port=22)
        lab_logger.info('server {0} is being provisioned by PXE re-booting... (might take several minutes- please wait)'.format(server))
        return server

    def create_servers(self):
        systems = self.__cobbler.find_system(dict(self.selector))
        if not systems:
            raise CobblerError('No associated systems selected by ' + '{0}'.format(self.selector))

        servers = [self.reboot_system(system) for system in systems]

        if not servers:
            raise CobblerError('No servers created')
        return servers

    def wait_for_servers(self):
        servers = self.create_servers()
        for server in servers:
            if self.force_pxe_boot:
                when_provided = server.run(command='cat ProvTime')
                if when_provided != self.prov_time:
                    raise CobblerError('Wrong provisioning attempt- timestamps are not matched')
            server.hostname = server.run(command='hostname')
        return servers
