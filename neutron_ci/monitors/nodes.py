import argparse
import requests
import urlparse
import urllib
import re
import os
import time
import sys


def offline(jenkins_url, name=None, skip_cause=None, recheck_time=30):
    nodes_url = urlparse.urljoin(jenkins_url, 'computer/api/json')
    cause = re.compile(skip_cause) if skip_cause else None
    is_offline = lambda n, c: \
        n['offline'] and not (c and c.search(n['offlineCauseReason']))

    nodes = requests.get(nodes_url).json()['computer']
    # Filter nodes by name
    if name:
        nodes = [n for n in nodes if name in n['displayName']]

    # Look for offline nodes
    res = list()
    offline_nodes = [n for n in nodes if is_offline(n, cause)]
    if offline_nodes:
        # Sleep for some time
        time.sleep(recheck_time)
        # Recheck status of offline nodes
        for off_node in offline_nodes:
            node_url = urlparse.urljoin(
                jenkins_url,
                'computer/{0}/api/json'.format(
                    urllib.quote(off_node['displayName'])))
            print("Get node info : {0}".format(node_url))
            r = requests.get(node_url)
            # Check status code because the node could be removed
            if r.status_code == 200:
                node = r.json()
                if is_offline(node, cause):
                    res.append(node)
    return res


def _offline(args):
    offline_nodes = offline(args.jenkins_url, args.name,
                            args.skip_cause, args.recheck_time)
    print os.linesep.join([str(n) for n in offline_nodes])
    sys.exit(len(offline_nodes))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='')

    offline_parser = subparsers.add_parser('offline', help='Sync DB')
    offline_parser.add_argument('--name', nargs='?', default='.*')
    offline_parser.add_argument('--skip-cause', nargs='?')
    offline_parser.add_argument('--jenkins-url')
    offline_parser.add_argument('--recheck-time', type=int, nargs='?',
                                default='30')
    offline_parser.set_defaults(func=_offline)
    args = parser.parse_args()
    args.func(args)
