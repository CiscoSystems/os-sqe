def get_ansible_inventory(pod):
    inventory = {}

    xrvr_username, xrvr_password = None, None
    xrvr_ips = []
    for node in pod.xrvr:
        ip, xrvr_username, xrvr_password = node.get_xrvr_ip_user_pass()
        xrvr_ips.append(ip)

    for node in [pod.mgmt] + pod.vts:
        ip, username, _ = node.get_ssh()
        inventory[node.id] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_private_key_file': pod.KEY_PRIVATE_PATH,
                                                      'xrvr_ip_mx': xrvr_ips, 'xrvr_username': xrvr_username, 'xrvr_password': xrvr_password}}

    for node in pod.vim_tors:
        ip, username, password = node.get_oob()
        inventory[node.get_id()] = {'hosts': [ip], 'vars': {'ansible_ssh_user': username, 'ansible_ssh_pass': password}}

    return inventory
