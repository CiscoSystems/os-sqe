if __name__ == '__main__':
    from lab.deployers.DeployerExistingOSP7 import DeployerExistingOSP7
    from lab.runners.RunnerHA import starter
    from lab.monitors.mon_cloud import start

    d = DeployerExistingOSP7({'cloud': 'g10', 'hardware-lab-config': 'g10'})
    cloud = d.deploy_cloud([])
    starter(item_description={'function': start, 'log-name': 'testXXX', 'cloud': cloud})
