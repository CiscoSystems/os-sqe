#!/usr/bin/env python
# _*_ coding: utf-8 _*_
import argparse
from datetime import datetime
from time import time


def main():
    from tools import run_tempest

    d_imported_modules = dict()
    for name, item in locals().items():
        if not name.startswith('__') and not name.startswith('d_imported_modules'):
            d_imported_modules[name] = item

    p = argparse.ArgumentParser(description='SQE CLI choose one of:')

    for name, module in d_imported_modules.iteritems():
        module.define_cli(p.add_subparsers().add_parser(name, formatter_class=argparse.ArgumentDefaultsHelpFormatter))

    args = p.parse_args()
    t1 = time()
    args.func(args)
    print 'Finished at', datetime.now(), 'took', time() - t1, 'secs'


if __name__ == "__main__":
    main()
