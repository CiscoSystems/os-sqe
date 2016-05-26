if __name__ == '__main__':
    from lab.providers.provider_existing_lab import ProviderExistingLab
    from lab.deployers.deployer_existing import DeployerExisting
    from lab.runners.runner_ha import starter
    from lab.monitors.vts import start

    p = ProviderExistingLab({'hardware-lab-config': 'artifacts/g7-2.yaml'})
    d = DeployerExisting({'cloud': 'ha-test', 'hardware-lab-config': 'artifacts/g7-2.yaml'})
    cloud = d.wait_for_cloud([])
    starter(item_description={'function': start, 'log-name': 'testXXX', 'cloud': cloud, 'is-show-details': True})
