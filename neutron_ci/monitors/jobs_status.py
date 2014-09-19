import argparse
import requests
import urlparse
import urllib
import sys


def check(jenkins_url, jobs, status, depth=10):
    jobs_url = map(
        lambda name: urlparse.urljoin(
            jenkins_url,
            'job/{0}/api/json'.format(urllib.quote(name))),
        jobs.split(','))

    # Get jobs data
    jobs = [requests.get(url).json() for url in jobs_url]
    flags = list()
    for job in jobs:
        print('Job {j} {l}'.format(j=job['displayName'], l='='*50))
        # Go through last <depth> builds
        for build in job['builds'][:depth]:
            url = urlparse.urljoin(build['url'], 'api/json')
            data = requests.get(url).json()
            print('Build {b}, status {s}, building {r}'.format(
                   b=data['number'],
                   s=data['result'],
                   r=data['building']
            ))
            f = data['result'] == status
            if f:
                flags.append(f)
                # Stop, there is at least one job with
                # expected status
                break
    # Return True if there is at least on job with failed builds
    return not any(flags)


def _check(args):
    r = check(args.jenkins_url, args.jobs, args.status, args.depth)
    sys.exit(r)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='')

    offline_parser = subparsers.add_parser('check', help='History check')
    offline_parser.add_argument('--jenkins-url')
    offline_parser.add_argument('--jobs')
    offline_parser.add_argument('--status', nargs='?', default='SUCCESS')
    offline_parser.add_argument('--depth', type=int, nargs='?', default=10)
    offline_parser.set_defaults(func=_check)
    args = parser.parse_args()
    args.func(args)
