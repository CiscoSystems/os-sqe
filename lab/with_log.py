class WithLogMixIn(object):

    @staticmethod
    def log_to_artifact(name, body):
        from lab.with_config import open_artifact

        with open_artifact(name, 'w') as f:
            f.write(body)

    def _format_single_cmd_output(self, cmd, ans):
        return 80 * 'v' + '\n' + self.__repr__() + '> ' + cmd + '\n' + 80 * '^' + '\n' + ans + '\n' + 80 * '-' + '\n\n'

    @staticmethod
    def upload_artifacts_to_our_server():
        """Store $REPO/*.log and $REPO/artifacts/* on file storage server"""
        from lab import logger
        from lab.nodes.server import LabServer

        destination_dir = '{0}-{1}'.format(logger.JENKINS_TAG, logger.REPO_TAG)
        server = LabServer(node_id='our_storage', ip='172.29.173.233', username='localadmin', password='ubuntu', lab=None, name='FileStorage')
        server.run(command='mkdir -p /var/www/logs/{0}'.format(destination_dir))
        server.put(local_path='*.log', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)
        server.put(local_path='artifacts/*', remote_path='/var/www/logs/' + destination_dir, is_sudo=False)

    @staticmethod
    def _form_log_grep_cmd(log_files, regex=None, minutes=0):
        """regex: 'string: some regexp to be used in grep, empty means all',
        'minutes': 'int: 10 -> filter out all messages older then 10 minutes ago, 0 means no filter'}
        """

        cmd = 'sed -n "/^$(date +%Y-%m-%d\ %H:%M --date="{min} min ago")/, /^$(date +%Y-%m-%d\ %H:%M)/p" '.format(min=minutes) if minutes else 'cat '
        cmd += log_files
        cmd += ' | grep ' + regex if regex else ''
        return cmd
