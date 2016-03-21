from lab.server import Server


class CobblerServer(Server):
    def configure_for_osp7(self):
        import xmlrpclib
        from lab.time_func import time_as_string
        from lab.logger import lab_logger

        lab_logger.info('(Re)creating cobbler profile')
        director = self.lab().get_director()

        ipmi_ip, ipmi_username, ipmi_password = director.get_ipmi()
        director_ip, _, _, _ = director.get_ssh()
        _, user_gw, user_mask, _, _ = self.lab().get_user_net_info()

        cobbler = xmlrpclib.Server(uri="http://{host}/cobbler_api".format(host=self._ip))

        token = cobbler.login(self._username, self._password)
        handle = cobbler.get_system_handle('{0}-DIRECTOR'.format(self.lab()), token)

        cobbler.modify_system(handle, 'comment', 'This system is created by {0} for LAB{1} at {2}'.format(__file__, self.lab(), time_as_string()), token)
        cobbler.modify_system(handle, 'hostname', director.hostname(), token)
        cobbler.modify_system(handle, 'gateway', str(user_gw), token)

        for nic in director.get_nics():
            cobbler.modify_system(handle, 'modify_interface', {'macaddress-{0}'.format(nic.get_name()): nic.get_mac()}, token)
            if nic.get_name() == 'user':
                cobbler.modify_system(handle, 'modify_interface', {'ipaddress-{0}'.format(nic.get_name()): str(director_ip),
                                                                   'static-{0}'.format(nic.get_name()): True,
                                                                   'subnet-{0}'.format(nic.get_name()): str(user_mask)}, token)

        cobbler.modify_system(handle, 'power_address', str(ipmi_ip), token)
        cobbler.modify_system(handle, 'power_user', ipmi_username, token)
        cobbler.modify_system(handle, 'power_pass', ipmi_password, token)
        lab_logger.info('finished')
