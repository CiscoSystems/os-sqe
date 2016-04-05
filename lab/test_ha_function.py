if __name__ == '__main__':
    from lab.deployers.deployer_existing_osp7 import DeployerExistingOSP7
    from lab.runners.runner_ha import starter
    from lab.scenarios.sriov import start

    d = DeployerExistingOSP7({'cloud': 'g10', 'hardware-lab-config': 'g10'})
    cloud = d.wait_for_cloud([])
    starter(item_description={'function': start, 'log-name': 'testXXX', 'cloud': cloud, 'is-show-details': True})
