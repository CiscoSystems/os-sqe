from lab.nodes import LabNode
from lab.decorators import section


class Spirent(LabNode):

    def cmd(self, cmd):
        pass

    role = 'SPIRENT'

    def __init__(self,  node_id, role, lab):

        super(Spirent, self).__init__(node_id=node_id, role=role, lab=lab)

        self.__stc = None
        self._hardware_ports = None

    def __repr__(self):
        return u'SPIRENT'

    def set_hardware_ports(self, ip, port_ids):
        self._hardware_ports = ['{}/1/{}'.format(ip, x) for x in port_ids]

    @property
    def _stc(self):
        if self.__stc is None:
            self.__stc = self.connect_to_manager()
        return self.__stc

    @section(message='Connecting to session manager', estimated_time=40)
    def connect_to_manager(self):
        import os
        import importlib

        spirent_folder_path = '/home/kshileev/Spirent_TestCenter_4.69/Spirent_TestCenter_Application_Linux64Client'
        spirent_module_path = spirent_folder_path + '/API/Python'

        os.environ['STC_PRIVATE_INSTALL_DIR'] = spirent_folder_path

        with open(spirent_module_path + '/StcPython.py') as f:
            body = f.read()
        with open(os.path.join(os.path.dirname(__file__), 'StcPython.py'), 'w') as f:
            f.write(body)

        module = importlib.import_module('StcPython')
        klass = getattr(module, 'StcPython')
        stc = klass()
        self.log(message='version {}'.format(stc.get('system1', 'version')))
        stc.config("AutomationOptions", logTo="stcapi.log", logLevel="INFO")
        stc.perform("CSTestSessionConnect", host=self.get_oob()[0], TestSessionName="sqe_auto", CreateNewTestSession="true")
        stc.perform("TerminateBll", TerminateType="ON_LAST_DISCONNECT")
        return stc

    def run_test(self):
        from lab.with_config import WithConfig

        conf_file_name = WithConfig.get_artifact_file_path('test.tcc')
        r = self._stc.perform("LoadFromDatabaseCommand", DatabaseConnectionString=conf_file_name)
        self.log('{} loaded: {}'.format(conf_file_name, r))
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
        sqe_spirent_db = 'sqe-spirent.db'
        self._stc.perform("SaveResult", CollectResult="TRUE", SaveDetailedResults="TRUE", DatabaseConnectionString=sqe_spirent_db, OverwriteIfExist="TRUE")

if __name__ == '__main__':
    s = Spirent(node_id='sp1', role=Spirent.role, lab='fake_lab')
    s.set_oob_creds(ip='172.29.74.4', username='admin', password='spt_admin')
    s.set_hardware_ports('172.29.68.53', [7, 8])
    s.run_test()

'''
    Manual step: download to our file storage a "Spirent TestCenter Virtual LabServer, v4.69 for Hypervisor - QEMU/KVM" in Archived Release -> Spirent TestCenter -> Virtual -> Hypervisor - QEMU/KVM
'''