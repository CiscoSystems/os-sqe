from lab.test_case_worker import TestCaseWorker
from lab.decorators import section


class VtsAddCompute(TestCaseWorker):

    def check_arguments(self):
        pass
    
    @section('Setup')
    def setup_worker(self):
        pass
    
    @section('Running test')
    def loop_worker(self):
        import os
        import random
        import yaml

        tag = self.pod.mgm.exe('cat /etc/cisco-mercury-release')
        setup_data_folder = "/root/installer-{tag}/openstack-configs".format(tag=tag)
        setup_data_path = os.path.join(setup_data_folder, 'setup_data.yaml')
        setup_data_orig_path = os.path.join(setup_data_folder, 'setup_data.yaml.orig')

        setup_data_orig = self.pod.mgm.exe('cat {0}'.format(setup_data_orig_path), is_warn_only=True)
        setup_data = self.pod.mgm.exe('cat {0}'.format(setup_data_path))

        if 'No such file' in setup_data_orig:
            raise Exception('There is no {0}. Could not add compute node'.format(setup_data_orig_path))

        setup_data_orig = yaml.load(setup_data_orig)
        setup_data = yaml.load(setup_data)

        computes_amount = len(setup_data['ROLES']['compute'])
        if computes_amount == len(setup_data_orig['ROLES']['compute']):
            raise Exception('All computes are already in use. Could not add compute')

        compute_name = random.choice(list(set(setup_data_orig['ROLES']['compute']) - set(setup_data['ROLES']['compute'])))
        setup_data['ROLES']['compute'].append(compute_name)
        setup_data['SERVERS'][compute_name] = setup_data_orig['SERVERS'][compute_name]

        self.pod.mgm.exe('rm -rf {0}'.format(setup_data_path))
        self.pod.mgm.file_append(setup_data_path, yaml.dump(setup_data, default_flow_style=False))

        self.pod.mgm.exe('cd /root/installer-{tag} && ./runner/runner.py -y -s 1,3 --add-computes {name} '.format(tag=tag, name=compute_name))
