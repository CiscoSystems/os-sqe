from lab.nodes import LabNode
from lab.decorators import section


class Spirent(LabNode):

    def cmd(self, cmd):
        pass

    role = 'SPIRENT'

    def __init__(self,  node_id, role, lab):
        from lab.with_config import WithConfig

        super(Spirent, self).__init__(node_id=node_id, role=role, lab=lab)

        self.__stc = None
        self._hardware_ports = None
        self._test_config_file_name = WithConfig.get_remote_store_file_to_artifacts('spirent/{}.tcc'.format(self.get_lab_id()))
        self._results_file_name = WithConfig.get_artifact_file_path('spirent-{}.db'.format(self.get_lab_id()))

    def __repr__(self):
        return u'SPIRENT'

    def set_hardware_ports(self, ip, port_ids):
        self._hardware_ports = ['{}/1/{}'.format(ip, x) for x in port_ids]

    @property
    def _stc(self):
        import os
        import importlib

        if self.__stc is None:
            spirent_folder_path = '/home/kshileev/Spirent_TestCenter_4.69/Spirent_TestCenter_Application_Linux64Client'

            os.environ['STC_PRIVATE_INSTALL_DIR'] = spirent_folder_path

            with open(spirent_folder_path + '/API/Python/StcPython.py') as f:
                body = f.read()
            with open(os.path.join(os.path.dirname(__file__), 'StcPython.py'), 'w') as f:
                f.write(body)

            module = importlib.import_module('StcPython')
            klass = getattr(module, 'StcPython')
            self.__stc = klass()
            self.log(message='version {}'.format(self.__stc.get('system1', 'version')))
            self.__stc.config("AutomationOptions", logTo="stcapi.log", logLevel="INFO")
        return self.__stc

    @section(message='Connecting to session manager', estimated_time=40)
    def connect_to_manager(self):

        self._stc.perform("CSTestSessionConnect", host=self.get_oob()[0], TestSessionName="sqe_auto", CreateNewTestSession="true")
        self._stc.perform("TerminateBll", TerminateType="ON_LAST_DISCONNECT")

    def run_test(self):
        self.connect_to_manager()
        r = self._stc.perform("LoadFromDatabaseCommand", DatabaseConnectionString=self._test_config_file_name)
        self.log('{} loaded: {}'.format(self._test_config_file_name, r))
        project = self._stc.get("system1", "children-project")
        vports_string = self._stc.get("system1.project", "children-port")
        self.log('project: {} has {}'.format(project, vports_string))
        vports = vports_string.split(' ')
        for vport, hport in zip(vports, self._hardware_ports):
            vport_location = self._stc.get(vport, 'location')
            self.log('vport={} vport_location={} hport={}'.format(vport, vport_location, hport))
            self._stc.config(vport, location=hport)
            self._stc.config(vport + ".generator.generatorconfig", fixedload=1000, loadunit="FRAMES_PER_SECOND")

        self._stc.subscribe(Parent=project, ConfigType="Generator", resulttype="GeneratorPortResults")
        self._stc.subscribe(Parent=project, ConfigType="Analyzer", resulttype="AnalyzerPortResults")
        self.log('subscribed to results')

        self._stc.perform("AttachPorts", AutoConnect="true", PortList=vports)

        # self._stc.perform("L2LearningStartCommand", HandleList=' '.join(vports))

        self.run_traffic(10)
        self.save_results()

    @section(message='running traffic', estimated_time=10)
    def run_traffic(self, traffic_time=10):
        import time

        self._stc.perform("GeneratorStartCommand")
        time.sleep(traffic_time)
        self._stc.perform("GeneratorStopCommand")

    @section(message='Saving results', estimated_time=40)
    def save_results(self):
        self._stc.perform("SaveResult", CollectResult="TRUE", SaveDetailedResults="TRUE", DatabaseConnectionString=self._results_file_name, OverwriteIfExist="TRUE")

    @section(message='Analysing results', estimated_time=10)
    def analyze_results(self):

        pathes = self._stc.perform("QueryResult", DatabaseConnectionString=self._results_file_name)
        for path in pathes:
            pass

if __name__ == '__main__':
    s = Spirent(node_id='sp1', role=Spirent.role, lab='g7-2')
    s.set_oob_creds(ip='172.29.74.4', username='admin', password='spt_admin')
    s.set_hardware_ports('172.29.68.53', [5, 6])
    # s.run_test()
    s.analyze_results()

'''
    Manual step: download to our file storage a "Spirent TestCenter Virtual LabServer, v4.69 for Hypervisor - QEMU/KVM" in Archived Release -> Spirent TestCenter -> Virtual -> Hypervisor - QEMU/KVM
'''