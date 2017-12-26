from lab.base_lab import LabWorker


class DeployerExistingLight(LabWorker):

    @staticmethod
    def sample_config():
        return '1.2.3.4'

    def __init__(self, pod_name):
        self.pod_name = pod_name

    def __call__(self, *args, **kwargs):
        from lab.cloud.openstack import OS
        from lab.laboratory import Laboratory

        mgm = Laboratory.create(lab_name=self.pod_name, is_mgm_only=True)
        return OS(name=self.pod_name, mediator=mgm, openrc_path='openrc')
