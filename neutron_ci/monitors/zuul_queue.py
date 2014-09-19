import argparse
import requests
import urlparse
import urllib
import sys
import datetime


def check(zuul_url, queue, jenkins_url, jobs, off_time=60*60):
    jobs_url = map(
        lambda name: urlparse.urljoin(
            jenkins_url,
            'job/{0}/lastBuild/api/json'.format(urllib.quote(name))),
        jobs.split(','))
    zuul_status_url = urlparse.urljoin(zuul_url, 'status.json')
    off_time = datetime.timedelta(seconds=off_time)

    status = requests.get(zuul_status_url).json()
    if 'pipelines' not in status and not status['pipelines']:
        raise Exception('There are no pipelines')
    status = filter(lambda p: p['name'] == queue, status['pipelines'])
    if not status:
        raise Exception('There is no such pipeline')
    status = status[0]

    flag = len(status['change_queues'][0]['heads']) == 0
    if flag:
        print("Zuul queue is empty. We should check last builds")
        now = datetime.datetime.now()
        job_flags = list()
        for job_url in jobs_url:
            data = requests.get(job_url).json()
            timestamp = datetime.datetime.fromtimestamp(data['timestamp'] / 1000)
            job_flags.append(now - timestamp < off_time)
        flag = flag and not any(job_flags)
    return flag


def _check(args):
    r = check(args.zuul_url, args.queue, args.jenkins_url, args.jobs,
              args.off_time)
    sys.exit(r)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='')

    offline_parser = subparsers.add_parser('check', help='Queue check')
    offline_parser.add_argument('--zuul-url')
    offline_parser.add_argument('--queue')
    offline_parser.add_argument('--jenkins-url')
    offline_parser.add_argument('--jobs')
    offline_parser.add_argument('--off-time', type=int, nargs='?',
                                default=60 * 60)
    offline_parser.set_defaults(func=_check)
    args = parser.parse_args()
    args.func(args)
