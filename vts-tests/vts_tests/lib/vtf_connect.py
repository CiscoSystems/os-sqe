import re

from vts_tests.lib import mercury_node_connect


class VtfConnect(mercury_node_connect.MercuryNodeConnect):

    def __init__(self, *args):
        super(VtfConnect, self).__init__(*args)

        # Go inside VTF container
        vtf_container_name = self.get_container_name('neutron-vtf')
        self.run('in_container {0}'.format(vtf_container_name))

        # Connect to vpp
        self._prompt_string = 'vpp#'
        self.run('telnet 0 5002')
        self.run('set terminal pager off')

    def show_ip_fib(self):
        return self.run('show ip fib')

    def show_int(self):
        return self.run('show int')

    def is_BondEthernet0_up(self):
        show_int = self.show_int()
        return re.search('BondEthernet0\s+\d+\s+up', show_int) is not None

