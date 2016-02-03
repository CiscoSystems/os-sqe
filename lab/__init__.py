from fabric.api import local, hide, settings

with hide('running', 'warnings'):
    with settings(warn_only=True):
        REPO_TAG = local('git describe', capture=True)
        if not REPO_TAG:
            REPO_TAG = local('git show HEAD --pretty="%h"', capture=True)