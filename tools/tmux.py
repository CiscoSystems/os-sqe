#!/usr/bin/env python
def main():
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


if __name__ == '__main__':
    main()
