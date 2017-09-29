from lab.test_case_worker import TestCaseWorker


class BashCmdMonitor(TestCaseWorker):

    # noinspection PyAttributeOutsideInit
    def setup_worker(self):
        import validators
        from lab.nodes.lab_server import LabServer

        self._cmd = self._kwargs['cmd']

        if validators.ipv4(self._ip):
            self._node = LabServer(node_id='Server{}'.format(self._ip), role='vtc', lab=None, hostname='NoDefined')
            self._node.set_ssh_creds(ip=self._ip, username=self._username, password=self._password)
        else:
            lab = self._cloud.mediator.lab()
            self._node = lab.get_nodes_by_id(self._ip)

    def loop_worker(self):
        res = self._node.exe(self._cmd, warn_only=True)
        self._log.info('node={0}, result={1}'.format(self._node, ''.join(res)))
