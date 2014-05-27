import argparse
import xml.etree.ElementTree as ET


class JUnitXML:
    def __init__(self, filepath):
        self._file_path = filepath
        self._xml_tree = None
        self._test_suite = None

    @property
    def xml_tree(self):
        if not self._xml_tree:
            self._xml_tree = ET.parse(self._file_path)
        return self._xml_tree

    @property
    def test_suite(self):
        if not self._test_suite:
            self._test_suite = JUnitTestSuite(self.xml_tree.getroot())
        return self._test_suite

    def save(self, filepath):
        self.xml_tree.write(filepath)


class JUnitTestSuite(object):
    def __init__(self, xml):
        self.xml = xml

    def filter_test_cases(self, status):
        tcs = [test_case for test_case in self.xml
               if JUnitTestCase(test_case).status != status]
        self.remove(tcs)

    def remove(self, test_cases):
        [self.xml.remove(tc) for tc in test_cases]

    def get_test_cases_dict(self, keys=('classname', 'name', 'status')):
        r = dict()
        for testcase_xml in self.xml:
            test_case = JUnitTestCase(testcase_xml)
            key = tuple(getattr(test_case, k) for k in keys)
            r[key] = test_case
        return r


class JUnitTestCase(object):
    def __init__(self, xml):
        self.xml = xml

    @property
    def status(self):
        children = self.xml.getchildren()
        if len(children) != 0:
            return children[0].tag
        return 'pass'

    @property
    def classname(self):
        return self.xml.attrib['classname']

    @property
    def name(self):
        return self.xml.attrib['name']

    @property
    def time(self):
        return self.xml.attrib['time']


def junit_difference(args):
    x1 = JUnitXML(args.files[0])
    x2 = JUnitXML(args.files[1])

    x1_cases = x1.test_suite.get_test_cases_dict()
    x2_cases = x2.test_suite.get_test_cases_dict()

    keys = set(x1_cases.keys()) - set(x2_cases.keys())
    tcs = [x1_cases[key].xml for key in set(x1_cases.keys()) - keys]

    x1.test_suite.remove(tcs)
    x1.save(args.outfile)


def junit_filter(args):
    junit = JUnitXML(args.file)
    junit.test_suite.filter_test_cases(args.status)
    junit.save(args.outfile)


parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(help='')
diff_parser = subparsers.add_parser('difference', help='Difference')
diff_parser.add_argument('files', nargs=2, help='JUnit xml files')
diff_parser.add_argument('--outfile', nargs='?', default='junit.xml')
diff_parser.set_defaults(func=junit_difference)
diff_parser.set_defaults(print_help=diff_parser.print_help)

filter_parser = subparsers.add_parser('filter', help='Filter')
filter_parser.add_argument('file', help='JUnit xml file')
filter_parser.add_argument('--status', default='failure', help='Test case result',
                           choices=['pass', 'skipped', 'error', 'failure'])
filter_parser.add_argument('--outfile', nargs='?', default='junit.xml')
filter_parser.set_defaults(func=junit_filter)
filter_parser.set_defaults(print_help=filter_parser.print_help)

args = parser.parse_args()

if __name__ == '__main__':
    args.func(args)
