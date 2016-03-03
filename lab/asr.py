from lab_node import LabNode


class Asr(LabNode):
    def cmd(self, command):
        from fabric.api import settings, run

        with settings(host_string='{user}@{ip}'.format(user=self._username, ip=self._ip), password=self._password, connection_attempts=50, warn_only=False):
            return run(command, shell=False)

    def configure_for_osp7(self, topology):
        return None
