#!/usr/bin/env python
import os
import sys
import requests
import json
import xml.etree.ElementTree as Et

__author__ = 'sshnaidm'

STYLE = """
<style>
table {
    font-family:Arial, Helvetica, sans-serif;
    color:#666;
    font-size:13px;
    text-shadow: 1px 1px 0px #fff;
    background:#eaebec;
    margin:20px;
    border:#ccc 1px solid;

    -moz-border-radius:3px;
    -webkit-border-radius:3px;
    border-radius:3px;

    -moz-box-shadow: 0 1px 2px #d1d1d1;
    -webkit-box-shadow: 0 1px 2px #d1d1d1;
    box-shadow: 0 1px 2px #d1d1d1;
}
table th {
    padding:21px 25px 22px 25px;
    border-top:1px solid #fafafa;
    border-bottom:1px solid #e0e0e0;

    background: #ededed;
    background: -webkit-gradient(linear, left top, left bottom, from(#ededed), to(#ebebeb));
    background: -moz-linear-gradient(top,  #ededed,  #ebebeb);
}
table th:first-child {
    text-align: left;
    padding-left:20px;
}
table tr:first-child th:first-child {
    -moz-border-radius-topleft:3px;
    -webkit-border-top-left-radius:3px;
    border-top-left-radius:3px;
}
table tr:first-child th:last-child {
    -moz-border-radius-topright:3px;
    -webkit-border-top-right-radius:3px;
    border-top-right-radius:3px;
}
table tr {
    text-align: center;
    padding-left:20px;
}
table td:first-child {
    text-align: left;
    padding-left:20px;
    border-left: 0;
}
table td {
    padding:18px;
    border-top: 1px solid #ffffff;
    border-bottom:1px solid #e0e0e0;
    border-left: 1px solid #e0e0e0;

    background: #fafafa;
    background: -webkit-gradient(linear, left top, left bottom, from(#fbfbfb), to(#fafafa));
    background: -moz-linear-gradient(top,  #fbfbfb,  #fafafa);
}
table tr.even td {
    background: #f6f6f6;
    background: -webkit-gradient(linear, left top, left bottom, from(#f8f8f8), to(#f6f6f6));
    background: -moz-linear-gradient(top,  #f8f8f8,  #f6f6f6);
}
table tr:last-child td {
    border-bottom:0;
}
table tr:last-child td:first-child {
    -moz-border-radius-bottomleft:3px;
    -webkit-border-bottom-left-radius:3px;
    border-bottom-left-radius:3px;
}
table tr:last-child td:last-child {
    -moz-border-radius-bottomright:3px;
    -webkit-border-bottom-right-radius:3px;
    border-bottom-right-radius:3px;
}
table tr:hover td {
    background: #f2f2f2;
    background: -webkit-gradient(linear, left top, left bottom, from(#f2f2f2), to(#f0f0f0));
    background: -moz-linear-gradient(top,  #f2f2f2,  #f0f0f0);
}
.pass {color:green}
.fail {color:red}
.skip {color:blue}
</style>
"""

TOPOS = {
    "2role": {"name": "2 Role", "job": "2role_tempest_cisco"},
    "aio": {"name": "All In One", "job": "AIOa_tempest_cisco"},
    "fullha": {"name": "Full HA", "job": "full_ha"}
}


def make_links(data):
    if "TRIGGERED_JOB_NAMES" in os.environ:
        jobs = os.environ["TRIGGERED_JOB_NAMES"].split(",")
    else:
        raise Exception("Script should be run in Jenkins environment!")
    for job in jobs:
        link = (os.environ["JENKINS_URL"] + "job/" +
                job + "/" + os.environ["TRIGGERED_BUILD_NUMBER_" + job] +
                "/testReport/")
        data_link = ("http://172.29.173.228:8080/" + job + "/" +
                     os.environ["TRIGGERED_BUILD_NUMBER_" + job])
        topo = next(iter([i for i in TOPOS if TOPOS[i]["job"] == job]), None)
        if not topo:
            raise Exception("Running jobs are inconsistent with configuration")
        if topo in data:
            data[topo]["results_link"] = link
            data[topo]["data_link"] = data_link
    return data


def check_regression(data):
    EMPTY_REGRESSION = {
        "failures_regression": "n/a",
        "passed_regression": "n/a",
        "skipped_regression": "n/a",
        "time_regression": "n/a",
        "total_regression": "n/a",
    }
    for topo in data:
        prev_link = (os.environ["JENKINS_URL"] + "job/" + TOPOS[topo]["job"] + "/" +
                     str(int(os.environ["TRIGGERED_BUILD_NUMBER_" + TOPOS[topo]["job"]]) - 1) +
                     "/testReport/api/json?pretty=true")
        try:
            result = json.loads(requests.get(prev_link).content)
            data[topo]["regress"] = {}
            data[topo]["regress"]["failures_regression"] = data[topo]["failures_number"] - int(result['failCount'])
            data[topo]["regress"]["passed_regression"] = data[topo]["passes_number"] - int(result['passCount'])
            data[topo]["regress"]["skipped_regression"] = data[topo]["skipped_number"] - int(result['skipCount'])
            data[topo]["regress"]["time_regression"] = data[topo]["time"] - float(result['duration'])
            data[topo]["regress"]["total_regression"] = data[topo]["tests_number"] - sum(
                [int(i) for i in (result['passCount'], result['failCount'], result['skipCount'])
                ])
            for reg in data[topo]["regress"]:
                number = data[topo]["regress"][reg]
                if number > 0:
                    data[topo]["regress"][reg] = "+" + str(number)
                else:
                    data[topo]["regress"][reg] = str(number)
        except Exception:
            data[topo]["regress"] = EMPTY_REGRESSION
    return data


def process_current(xmls):
    data = {}
    for xml in xmls:
        file_name = os.path.basename(xml)
        for topo in TOPOS:
            if topo in file_name:
                data[topo] = {"file": xml}
                break
        else:
            raise Exception("Can not recognize topology of file %s at path %s" % (file_name, xml))
        tree = Et.parse(xml)
        test_suite = tree.getroot()
        data[topo].update({"failures_number": int(test_suite.attrib['failures'])})
        data[topo].update({"tests_number": int(test_suite.attrib['tests'])})
        data[topo].update({"errors_number": int(test_suite.attrib['errors'])})
        data[topo].update({"time": float(test_suite.attrib['time'])})
        skipped = tree.findall(".//skipped")
        data[topo].update({"skipped_number": len(skipped)})
        data[topo].update({"passes_number": int(test_suite.attrib['tests']) - (
            int(test_suite.attrib['errors']) + int(test_suite.attrib['failures']) + len(skipped)
        )})
    return data


def process_current2(xmls):
    data = {}
    if "TRIGGERED_JOB_NAMES" in os.environ:
        jobs = os.environ["TRIGGERED_JOB_NAMES"].split(",")
    else:
        raise Exception("Script should be run in Jenkins environment!")
    for job in jobs:
        topo = next(iter([i for i in TOPOS if TOPOS[i]["job"] == job]), None)
        if not topo:
            raise Exception("Running jobs are inconsistent with configuration")
        current_link = (os.environ["JENKINS_URL"] + "job/" + TOPOS[topo]["job"] + "/" +
                     os.environ["TRIGGERED_BUILD_NUMBER_" + TOPOS[topo]["job"]] +
                     "/testReport/api/json?pretty=true")
        try:
            result = json.loads(requests.get(current_link).content)
            data[topo] = {}
            data[topo].update({"failures_number": int(result['failCount'])})
            data[topo].update({"passes_number": int(result['passCount'])})
            data[topo].update({"time": float(result['duration'])})
            data[topo].update({"skipped_number": int(result['skipCount'])})
            data[topo].update({"tests_number": sum(
                [int(i) for i in (result['passCount'], result['failCount'], result['skipCount'])]
            )})
        except Exception as e:
            print >> sys.stderr, "No current results from Jenkins API for %s : %s!" % (
                TOPOS[topo]["job"], os.environ["TRIGGERED_BUILD_NUMBER_" + TOPOS[topo]["job"]]
            )

    return data


def pretty_report(data):
    topos_template = "\n{style}\n".format(style=STYLE)
    failed_topo_template = """
<tr><td><strong>{name}</strong>:</td>
<td class="fail">FAILED TO TEST</td>
<td class="fail">FAILED TO TEST</td>
<td class="fail">FAILED TO TEST</td>
<td>N/A</td>
<td>N/A</td>
<td>N/A</td>
<td>N/A</td>
</tr>
"""
    table_row_template = """
<tr><td><strong>{name}</strong>:</td>
<td class="pass">{passes_number} ({regress[passed_regression]})</td>
<td class="fail">{failures_number} ({regress[failures_regression]})</td>
<td class="skip">{skipped_number} ({regress[skipped_regression]})</td>
<td>{tests_number} ({regress[total_regression]})</td>
<td><a href="{results_link}">[DETAILED REPORT]</a></td>
<td><a href="{data_link}">[TEST DATA FILES]</a></td>
<td>{time} sec</td>
</tr>
"""
    for topo in data:
        topos_template += table_row_template.format(
            name=TOPOS[topo]["name"],
            **data[topo])
    for topo in TOPOS:
        if topo not in data:
            topos_template += failed_topo_template.format(name=TOPOS[topo]["name"])
    main_template = """
<h2>COI CI report</h3>
<h3>build #{build_number} of {date}</h4>
    <table>
<tr>
<th>Topology</th>
<th class="pass">PASSED</th>
<th class="fail">FAILED</th>
<th class="skip">SKIPPED</th>
<th>TOTAL</th>
<th>RESULTS</th>
<th>FILES</th>
<th>Duration</th>
</tr>
{topos}
</table>
""".format(
        topos=topos_template,
        build_number=os.environ["BUILD_NUMBER"],
        date=os.environ["BUILD_ID"].split("_")[0])
    return main_template


def main():
    files = sys.argv[1:]
    xml_report = process_current2(files)
    links_report = make_links(xml_report)
    regression_report = check_regression(links_report)
    print pretty_report(regression_report)


if __name__ == '__main__':
    main()