from fabric.api import task, cd, run, settings
from fabric.context_managers import shell_env
from fabric.contrib.files import exists
from fabric.operations import get


# TODO rename file 'devstacks.yaml' into something more
@task
def report(jobs='devstacks.yaml', report_file='report.html', local_report_path='./reports/'):
    """fab jenkins_reports.report \t\t\t Gets report from jenkins in html format using yaml conf file.
        :param local_report_path:
        :param report_file:
        :param jobs:
    """
    from lab.logger import lab_logger

    lab_logger.info("Getting report with jobs yaml {}".format(jobs))
    user_name = 'localadmin'
    report_path = '/home/{user_name}/workspace/test_aggregator/openstack-sqe/tools/jenkins/job-helpers/'.format(user_name=user_name)
    with settings(user=user_name, password='ubuntu', host_string='172.29.172.165'):
        with cd(report_path):
            if exists('./{}'.format(report_file)):
                run('rm ./{}'.format(report_file))
            with shell_env(JENKINS_URL='http://172.29.173.72:8080/', REPORT_NAME='REPORT', MAKE_BUG_LIST='TRUE'):
                run('python coi_ci_reporter.py {yaml}>{report}'.format(yaml=jobs, report=report_file))
            get(remote_path=report_path + report_file, local_path=local_report_path + report_file)
