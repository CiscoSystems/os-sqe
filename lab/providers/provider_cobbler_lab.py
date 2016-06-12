from lab.providers import Provider


class ProviderCobblerLab(Provider):
    """Creates systems on cobbler for all lab nodes which sits on network marked as is-pxe.
        Checks that nodes indeed has proper NICs configured. Configure them if not. Then reboot all the systems"""
    def sample_config(self):
        return {'hardware-lab-config': 'some yaml with valid lab configuration'}

    def __init__(self, config):
        from lab.laboratory import Laboratory

        super(ProviderCobblerLab, self).__init__(config=config)
        self._lab = Laboratory(config_path=config['hardware-lab-config'])

    def wait_for_servers(self):
        from lab.cobbler import CobblerServer

        cobbler = self._lab.get_nodes_by_class(CobblerServer)[0]

        return cobbler.cobbler_deploy()
