import os
from os import path
import yaml

repo_dir = os.path.expanduser('~/repo/mercury/mercury/testbeds')
pod_names = filter(lambda x: x[0] not in ['.', 'R'], os.listdir(repo_dir))

dic = {}

for pod_name in pod_names:
    yaml_names = os.listdir(path.join(repo_dir, pod_name))
    for yaml_name in yaml_names:
        with open(path.join(repo_dir, pod_name, yaml_name)) as f:
            try:
                setup_data = yaml.load(f.read())
            except Exception:
                print pod_name + ' ' + yaml_name + ' is broken'
        if 'TESTING_MGMT_NODE_API_IP' not in setup_data:
            continue
        mgm_ip = setup_data['TESTING_MGMT_NODE_API_IP'].split('/')[0]
        if dic.get(pod_name, {'ip': mgm_ip})['ip'] != mgm_ip:
            print pod_name + ' already defines different mgm ip ' + dic[pod_name]
        dic[pod_name] = {'ip': mgm_ip, 'yaml': yaml_name}
print {x: y['ip'] for x,y in dic.items()}
