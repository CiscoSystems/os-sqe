__author__ = 'sshnaidm'


import sys
import xml.etree.ElementTree as Et

with open(sys.argv[1]) as f:
    xml = f.read()
exml = Et.fromstring(xml)

tmp_fails = [i.attrib["classname"] + "." + i.attrib["name"]
         for i in exml.getchildren()
         for z in i.getchildren()
         if i.getchildren()
         if "failure" in z.tag]
fails = [i for i in tmp_fails if "process-returncode" not in i]
if fails:
    print("\n".join(fails))
else:
    sys.exit()