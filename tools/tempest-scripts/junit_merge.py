#!/usr/bin/env python
#
#  Corey Goldberg, Dec 2012
#

import os
import sys
import xml.etree.ElementTree as Et
import itertools


def main():
    args = sys.argv[1:]
    if not args:
        usage()
        sys.exit(2)
    if '-h' in args or '--help' in args:
        usage()
        sys.exit(2)
    merge_results(args[:])


def merge_cases(cases):
    dicmap = {}
    for i in itertools.chain(*[case for case in cases]):
        name = i.attrib["classname"] + "___" + i.attrib["name"]
        if name in dicmap:
            dicmap[name].append(i)
        else:
            dicmap[name] = [i]
    new_dicmap = {}
    for i in dicmap:
        for case in dicmap[i]:
            if not case.getchildren():
                std_case = case
                break
        else:
            std_case = dicmap[i][-1]
        if (len(dicmap[i]) < len(sys.argv[1:]) and "setUpClass" in i) or "process-returncode" in i:
            pass
        else:
            new_dicmap[i] = std_case
    return sorted(new_dicmap.values())


def merge_results(xml_files):
    failures = []
    tests = []
    errors = []
    time = []
    cases = []

    for file_name in xml_files:
        tree = Et.parse(file_name)
        test_suite = tree.getroot()
        failures.append(int(test_suite.attrib['failures']))
        tests.append(int(test_suite.attrib['tests']))
        errors.append(int(test_suite.attrib['errors']))
        time.append(float(test_suite.attrib['time']))
        cases.append(test_suite.getchildren())

    new_root = Et.Element('testsuite')
    new_root.attrib['failures'] = '%s' % min(failures)
    new_root.attrib['tests'] = '%s' % max(tests)
    new_root.attrib['errors'] = '%s' % min(errors)
    new_root.attrib['time'] = '%s' % max(time)
    new_root.extend(merge_cases(cases))
    new_tree = Et.ElementTree(new_root)
    Et.dump(new_tree)


def usage():
    this_file = os.path.basename(__file__)
    print 'Usage:  %s results1.xml results2.xml' % this_file


if __name__ == '__main__':
    main()
