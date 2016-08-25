#!/usr/bin/env python
# Get dynamic inventory for ansible


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description='OpenStack Inventory Module')
    parser.add_argument('--lab', action='store_true', help='Use private address for ansible host')
    parser.add_argument('--refresh', action='store_true', help='Refresh cached information')
    parser.add_argument('--debug', action='store_true', default=False, help='Enable debug output')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true', help='List active servers')
    group.add_argument('--host', help='List details about the specific host')

    return parser.parse_args()


def main():
    import json
    import os
    from lab.laboratory import Laboratory

    os.environ['DISABLE_SQE_LOG'] = 'Yes'
    args = parse_args()
    l = Laboratory(config_path='g7-2.yaml')
    inventory = l.get_ansible_inventory()
    if args.list:
        output = json.dumps(inventory)
    elif args.host:
        output = inventory[args.host]
    else:
        output = 'Nothing to return'
    print(output)


if __name__ == '__main__':
    main()
