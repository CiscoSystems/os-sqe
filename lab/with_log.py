class WithLogMixIn(object):

    @staticmethod
    def log_to_artifact(name, body):
        from lab.with_config import open_artifact

        with open_artifact(name, 'w') as f:
            f.write(body)

    def _format_single_cmd_output(self, cmd, ans):
        return 80 * 'v' + '\n' + self.__repr__() + '> ' + cmd + '\n' + 80 * '^' + '\n' + ans + '\n' + 80 * '-' + '\n\n'
