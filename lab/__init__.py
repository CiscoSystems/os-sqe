import os
# from fabric.api import local, hide, settings
#
# with hide('running', 'warnings'):
#     with settings(warn_only=True):
#         REPO_TAG = local('git describe --always', capture=True)

OSP7_INFO = 'NA'
JENKINS_TAG = os.getenv('BUILD_TAG', 'NA')
