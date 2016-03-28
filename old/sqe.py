#!/usr/bin/env python


def import_modules():
    from tools import run_tempest, tempest_configurator, test_pairs_generator

    d_imported_modules = dict()
    for name, item in locals().items():
        if not name.startswith('__') and not name.startswith('d_imported_modules'):
            d_imported_modules[name] = item
    return d_imported_modules


def main():
    import argparse
    from datetime import datetime
    from time import time

    p = argparse.ArgumentParser(description='SQE CLI')
    sp = p.add_subparsers(title='commands')
    for name, module in import_modules().iteritems():
        module.define_cli(sp.add_parser(name=name,
                                        description=module.DESCRIPTION,
                                        help=module.DESCRIPTION,
                                        formatter_class=argparse.ArgumentDefaultsHelpFormatter))

    args = p.parse_args()
    t1 = time()
    args.func(args)
    print 'Finished at', datetime.now(), 'took', time() - t1, 'secs'


if __name__ == "__main__":
    main()
