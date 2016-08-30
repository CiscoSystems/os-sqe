def tmux():
    """Creates a number of config files for tmux utility"""
    import os
    from lab.laboratory import Laboratory
    from lab.with_config import ls_configs

    def form_new_window(ip, u, p, n, l):
        first_part = 'tmux new-window -t {lab}:{counter} -n {role} '.format(role=n, lab=l, counter=counter)
        cmd_part = '"sshpass -p {password} ssh {username}@{ip}"'.format(username=u, ip=ip, password=p)
        f.write(first_part + cmd_part + '\n')

    with open(os.path.expanduser('~/.tmux.conf'), 'w') as f:
        f.write('set -g prefix C-a\n')  # default Ctrl-a for Alt use m-
        f.write('set -g history-limit 5000\n')  # 5000 lines in scrolling
        f.write('set -g base-index 1\n')  # start numerating from 1

    with open(os.path.expanduser('~/tmux'), 'w') as f:

        for lab_config in ls_configs():
            lab = Laboratory(config_path=lab_config)
            name = lab_config.strip('.yaml')

            counter = 2
            f.write('tmux new-session -s {0} -n sqe -d\n'.format(name))

            director = lab.director()
            ucsm_ip, ucsm_username, ucsm_password = lab.ucsm_creds()
            n9k_ip1, n9k_ip2, n9k_username, n9k_password = lab.n9k_creds()

            form_new_window(ip=director.ip, u=director.username, p=director.password, n='di', l=name)
            counter += 1
            form_new_window(ip=ucsm_ip, u=ucsm_username, p=ucsm_password, n='fi', l=name)
            counter += 1
            form_new_window(ip=n9k_ip1, u=n9k_username, p=n9k_password, n='n9', l=name)
            counter += 1

        f.write('tmux select-window -t g10:1\n')
        f.write('tmux -2 attach-session -t g10\n')


def mtputty(lab):
    import os

    file_path = os.path.expanduser('~/MTPuTTY-{lab}.xml'.format(lab=lab))
    with open(file_path, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<MTPutty version="1.0">\n')

        f.write('\t<Servers>\n')
        f.write('\t\t<Putty>\n')

        f.write('\t\t\t<Node Type="0" Expanded="1">\n')
        f.write('\t\t\t\t<DisplayName>{lab_name}</DisplayName>\n'.format(lab_name=lab))

        for node in lab.get_nodes_by_class():
            ip, username, password = node.get_ssh()

            f.write('\t\t\t\t<Node Type="1">\n')
            f.write('\t\t\t\t\t<SavedSession>Default Settings</SavedSession>\n')
            f.write('\t\t\t\t\t<DisplayName>{node_name}</DisplayName>\n'.format(node_name=node.get_id()))
            f.write('\t\t\t\t\t<ServerName>{ip}</ServerName>\n'.format(ip=ip))
            f.write('\t\t\t\t\t<PuttyConType>4</PuttyConType>\n')
            f.write('\t\t\t\t\t<Port>0</Port>\n')
            f.write('\t\t\t\t\t<UserName>{username}</UserName>\n'.format(username=username))
            f.write('\t\t\t\t\t<PlainPassword>{password}</PlainPassword>\n'.format(password=password))
            f.write('\t\t\t\t\t<PasswordDelay>0</PasswordDelay>\n')
            f.write('\t\t\t\t\t<CLParams>{ip} -ssh -l {username} -pw *****</CLParams>\n'.format(ip=ip, username=username))
            f.write('\t\t\t\t\t<ScriptDelay>0</ScriptDelay>\n')
            f.write('\t\t\t\t</Node>\n')

        f.write('\t\t</Putty >\n')
        f.write('\t</Servers>\n')
    print('MTPuTTY config for lab {lab} written to {path}. Please import it!'.format(lab=l, path=file_path))


def mobaxterm(lab):
    import os
    from lab.nodes.n9k import Nexus
    from lab.nodes.fi import FI
    from lab.nodes.tor import Tor

    file_path = os.path.expanduser('~/mobaXterm-{lab}.mxtsessions'.format(lab=lab))
    with open(file_path, 'w') as f:
        f.write('[Bookmarks]\n')
        f.write('SubRep={lab_name}\n'.format(lab_name=lab))
        f.write('ImgNum=41\n')

        for node in lab.get_nodes_by_class():
            ip, username, _ = node.get_oob() if type(node) in [Tor, Nexus, FI] else node.get_ssh()

            f.write('{name} ({ip})= #132#0%{ip}%22%{username}%%0%-1%%%22%%0%0%Interactive shell%%%0%0%0%0%%1080%%0%0#MobaFont%10%0%0%0%15%236,236,236%0,0,0%180,180,192%0%-1%0%%xterm%-1%0%0,0,0%54,54,54%255,96,96%255,128,128%96,255,96%128,255,128%255,255,54%255,255,128%96,96,255%128,128,255%255,54,255%255,128,255%54,255,255%128,255,255%236,236,236%255,255,255%80%24%0%1%-1%<none>%#0\n'.format(
                name=node.get_id(), ip=ip, username=username
            ))

    print('mobaXterm config for lab {lab} written to {path}. Please import it!'.format(lab=l, path=file_path))


if __name__ == '__main__':
    import platform
    from lab.laboratory import Laboratory

    l = Laboratory(config_path='g7-2')

    if platform.system() == 'Windows':
        mtputty(l)
        mobaxterm(l)
    else:
        tmux()
