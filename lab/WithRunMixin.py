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
    def get_package_manager(server):
        possible_packages = ['apt-get', 'dnf', 'yum']
        for x in possible_packages:
            if WithRunMixin.run(command='whereis {0}'.format(x), server=server) != x + ':':
                return x
        raise RuntimeError('do not know which package manager to use: neither of {0} found'.format(possible_packages))

    @staticmethod
    def check_or_install_packages(package_names, server):
        for package_name in package_names.split():
            if WithRunMixin.run(command='whereis {0}'.format(package_name), server=server) == package_name + ':':
                pm = WithRunMixin.get_package_manager(server=server)
                WithRunMixin.run(command='sudo {0} install -y {1}'.format(pm, package_name), server=server)

    @staticmethod
    def clone_repo(repo_url, local_repo_dir=None, server=None):
        import urlparse

        local_repo_dir = local_repo_dir or urlparse.urlparse(repo_url).path.split('/')[-1].strip('.git')

        WithRunMixin.check_or_install_packages(package_names='git', server=server)
        WithRunMixin.run(command='test -d {0} || git clone -q {1} {0}'.format(local_repo_dir, repo_url), server=server)
        WithRunMixin.run(command='git pull -q', server=server, in_directory=local_repo_dir)
        return WithRunMixin.run(command='pwd', server=server, in_directory=local_repo_dir)

    def create_user(self, new_username, server):
        if not self.run(command='grep {0} /etc/passwd'.format(new_username), server=server, warn_only=True):
            encrypted_password = self.run(command='openssl passwd -crypt {0}'.format(server.password), server=server)
            self.run(command='sudo adduser -p {0} {1}'.format(encrypted_password, new_username), server=server)
            self.run(command='sudo echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(new_username), server=server)
            self.run(command='sudo chmod 0440 /etc/sudoers.d/{0}'.format(new_username), server=server)
        server.username = new_username
