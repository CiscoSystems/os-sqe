import re
from vts_tests.lib import shell_connect


class MercuryNodeConnect(shell_connect.ShellConnect):

    def reboot(self):
        self._shell_channel.send('reboot\n')
        self._shell_channel.close()

    def get_container_id(self, container_pattern, options='-a'):
        return self.run("docker ps {opts} | grep {pattern} | "
                        "awk '{{print $1}}'".format(opts=options, pattern=container_pattern))
    
    def get_container_name(self, container_pattern):
        return self.run("docker ps -a | grep {0} | awk '{{print $NF}}'".format(container_pattern))

    def get_process_id(self, container_pattern, pprocess_name):
        res = self.run("docker exec {0} pgrep -f {1}".format(container_pattern, pprocess_name))
        g = re.search('\d+', res)
        return g.group(0) if g else None

    def kill_process_inside_container(self, container_id, process_id):
        self.run('docker exec {cid} kill -9 {pid}'.format(cid=container_id, pid=process_id))

    def docker_stop(self, container_pattern):
        container_id = self.get_container_id(container_pattern)
        if not container_id:
            raise Exception('Container {0} not found.'.format(container_pattern))
        self.run('docker stop {0}'.format(container_id))