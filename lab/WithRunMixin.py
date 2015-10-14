import os
from lab.WithConfig import CONFIG_DIR


class WithRunMixin(object):
    PRIVATE_KEY = os.path.join(CONFIG_DIR, 'keys', 'private')

    @staticmethod
    def construct_settings(server, warn_only):
        kwargs = {'host_string': '{user}@{ip}'.format(user=server.username, ip=server.ip),
                  'connection_attempts': 50,
                  'warn_only': warn_only}
        if server.password == 'ssh_key':
            kwargs['key_filename'] = WithRunMixin.PRIVATE_KEY
        else:
            kwargs['password'] = server.password
        return kwargs

    @staticmethod
    def run(command, server=None, in_directory='.', warn_only=False):
        """Do run with possible sudo on remote server"""
        from fabric.api import run, local, sudo, settings, cd, lcd

        if not server:
            with lcd(in_directory):
                return local(command, capture=True)

        run_or_sudo = run
        if command.startswith('sudo '):
            command = command.replace('sudo ', '')
            run_or_sudo = sudo

        with settings(**WithRunMixin.construct_settings(server=server, warn_only=warn_only)):
            with cd(in_directory):
                result = run_or_sudo(command)
                return result

    @staticmethod
    def put(what, name, server, in_directory='.'):
        """Put given string as file to remote server"""
        from fabric.api import put, settings, cd
        from StringIO import StringIO

        use_sudo = True if name.startswith('/') else False
        with settings(**WithRunMixin.construct_settings(server=server, warn_only=False)):
            with cd(in_directory):
                return put(local_path=StringIO(what), remote_path=name, use_sudo=use_sudo)

    @staticmethod
    def wget_file(url, to_directory, checksum, server=None):
        loc = url.split('/')[-1]
        WithRunMixin.run(command='mkdir -p {0}'.format(to_directory), server=server)
        WithRunMixin.run(command='test -e  {loc} || wget -nv {url} -O {loc}'.format(loc=loc, url=url), server=server, in_directory=to_directory)
        calc_checksum = WithRunMixin.run(command='sha256sum {loc}'.format(loc=loc), server=server, in_directory=to_directory)
        if calc_checksum.split()[0] != checksum:
            WithRunMixin.run(command='rm {0}'.format(loc), server=server, in_directory=to_directory)
            raise RuntimeError('I deleted image {0} since it is broken (checksum is not matched). Re-run the script'.format(loc))
        return loc

    @staticmethod
    def is_dpkg(server):
        return WithRunMixin.run(command='whereis dpkg', server=server) != 'dpkg:'

    @staticmethod
    def check_or_install_package(package_name, server):
        if WithRunMixin.run(command='whereis {0}'.format(package_name), server=server) == package_name + ':':
            if WithRunMixin.is_dpkg(server=server):
                WithRunMixin.run(command='sudo rm /var/lib/apt/lists/* -vrf', server=server)  # This is workaround for ubuntu update fails with Hash Sum mismatch on some packages
                WithRunMixin.run(command='sudo apt-get -y -q update && apt-get install -y -q {0}'.format(package_name), server=server)
            else:
                WithRunMixin.run(command='sudo dnf install -y {0}'.format(package_name), server=server)

    @staticmethod
    def clone_repo(repo_url, server):
        import urlparse

        local_repo_dir = urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        WithRunMixin.check_or_install_package(package_name='git', server=server)
        WithRunMixin.run(command='test -d {0} || git clone -q {1}'.format(local_repo_dir, repo_url), server=server)
        WithRunMixin.run(command='git pull -q', server=server, in_directory=local_repo_dir)
        return local_repo_dir
