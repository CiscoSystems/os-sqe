#!/usr/bin/env python
from collections import OrderedDict
import os
import sys
import requests
import json
import xml.etree.ElementTree as Et
import time
import yaml

cachedir = "/home/localadmin/.launchpadlib/cache/"
from launchpadlib.launchpad import Launchpad

launchpad = Launchpad.login_anonymously('just testing', 'production', cachedir)

__author__ = 'sshnaidm'
BUG_DATA_LOCATION = "http://172.29.173.233/nightly/bug_data.json"
LOG_SERVER_LOCATION = "http://172.29.173.228:8080/"
NEUTRON_GITHUB_URL = {
"api": "https://api.github.com/repos/openstack/neutron/git/refs/heads/master",
"url": "https://github.com/openstack/neutron"}
INTERNAL_NEUTRON_GITHUB_URL = {
"api": "https://api.github.com/repos/cisco-openstack/neutron/git/refs/heads/staging",
"url": "https://github.com/cisco-openstack/neutron"}
TEMPEST_GITHUB_URL = {
"api": "https://api.github.com/repos/cisco-openstack/tempest/git/refs/heads/proposed",
"url": "https://github.com/cisco-openstack/tempest"}
GITHUB_URLS = {0: {
"api": "https://api.github.com/repos/openstack/neutron/git/refs/heads/master?client_id=ebagdasa&client_secret=dd083d7427353c1d410a4d069e2d895d5b7e641d",
"url": "https://github.com/openstack/neutron"},
               3: {
               "api": "https://api.github.com/repos/openstack-dev/devstack/git/refs/heads/master?client_id=ebagdasa&client_secret=dd083d7427353c1d410a4d069e2d895d5b7e641d",
               "url": "https://github.com/openstack-dev/devstack"},
               4: {
               "api": "https://api.github.com/repos/cisco-openstack/tempest/git/refs/heads/proposed?client_id=ebagdasa&client_secret=dd083d7427353c1d410a4d069e2d895d5b7e641d",
               "url": "https://github.com/cisco-openstack/tempest"}
}

AGGREGATOR_JOB_NAME = "test_aggregator"
STYLE = """
<style>
body{
    font-family:Calibri;
    color:#000;
    font-size:14px;
}
.pass {color:green}
.fail {color:red}
.skip {color:blue}
</style>
"""
failed_topo_template = """
<tr><td><strong>{name}</strong>:</td>
<td class="fail">FAILED TO TEST</td>
<td class="fail">FAILED TO TEST</td>
<td class="fail">FAILED TO TEST</td>
<td>N/A</td>
<td>N/A</td>
<td align=justify>{total_time_str}</td>
</tr>
"""
failed_topo_template2 = """
<tr><td><strong>{name}</strong>:</td>
<td class="fail">FAILED TO TEST</td>
<td class="fail">FAILED TO TEST</td>
<td class="fail">FAILED TO TEST</td>
<td>N/A</td>
<td align=justify>{total_time_str}</td>
</tr>
"""
table_row_template = """
<tr><td><strong>{name}</strong>:</td>
<td class="pass">{passes_number} ({regress[passed_regression]})</td>
<td class="fail">{failures_number} ({regress[failures_regression]})</td>
<td class="skip">{skipped_number} ({regress[skipped_regression]})</td>
<td>{tests_number} ({regress[total_regression]})</td>
<td><a href="{results_link}">[Jenkins]</a>, <a href="{data_link}">[Logs]</a></td>
<td align=justify>{total_time_str}</td>
</tr>
"""
# <strong>Tests:</strong> {time_str}<br>
table_row_template2 = """
<tr><td><strong>{name}</strong>:</td>
<td class="pass">{passes_number} ({regress[passed_regression]})</td>
<td class="fail">{failures_number} ({regress[failures_regression]})</td>
<td class="skip">{skipped_number} ({regress[skipped_regression]})</td>
<td>{tests_number} ({regress[total_regression]})</td>
<td><a href="{results_link}">[Jenkins]</a></td>
<td align=justify>{total_time_str}</td>
</tr>
"""
table_row_template3 = """
<tr><td><strong>{name}</strong>:</td>
<td class="pass">{passes_number} ({regress[passed_regression]})</td>
<td class="fail">{failures_number} ({regress[failures_regression]})</td>
<td class="skip">{skipped_number} ({regress[skipped_regression]})</td>
<td>{tests_number} ({regress[total_regression]})</td>
<td><a href="{results_link}">[Jenkins]</a></td>
<td align=justify>{total_time_str}</td>
</tr>
"""
table_row_template4 = """
<tr><td><strong>{name}</strong>:</td>
<td class="pass">{passes_number} (+{regress[passed_regression][pos]},-{regress[passed_regression][neg]})</td>
<td class="fail">{failures_number} (+{regress[failures_regression][pos]},-{regress[failures_regression][neg]})</td>
<td class="skip">{skipped_number} (+{regress[skipped_regression][pos]},-{regress[skipped_regression][neg]})</td>
<td>{tests_number} (+{regress[total_regression][pos]},-{regress[total_regression][neg]})</td>
<td><a href="{results_link}">[Jenkins]</a></td>
<td align=justify>{total_time_str}</td>
</tr>
"""
main_template_demo = """
<table border="1">
<tr>
<th>Description</th>
<th class="pass">PASSED</th>
<th class="fail">FAILED</th>
<th class="skip">SKIPPED</th>
<th>TOTAL</th>
<th>ARTIFACTS</th>
<th>Duration</th>
</tr>
{topos}
</table>
"""
table_row_bug_template = """
<tr>
    <td>{testNo}</td>
    <td align='left' style='color:{color2}'>{testName}</td>
    <td style='color:{color}'>{bugNo}</td>
</tr>
    """
table_bug_template = """
<h3>Tests for {job}</h3></br>
<table>
<tr>
    <td>N</td>
    <td align='left'>Testname</td>
    <td>Bug tracker/status</td>
</tr>
{rows}
</table>
"""
table_bug_template2 = """
<h3>Tests for {job}</h3>
<p style='color:green'>All Passed</p>
</table>
"""
TOPOS = None
bug_stats = {}


def str_time(t):
    return time.strftime("%H h %M min", time.gmtime(int(t)))


def get_failed_tests(data):
    failed_tests_table = OrderedDict({})
    bug_list = requests.get(BUG_DATA_LOCATION).json()
    for job in data:
        failed_tests = []
        fixed_test_cases = []
        regressed_test_cases = []
        if "results_link" not in data[job] or job == "total":
            continue
        json_test_results = requests.get(
            data[job]["results_link"] + "api/json?pretty=true").json()
        failed_tests_amount = 0
        for test_case in json_test_results["suites"][0]["cases"]:
            bugno = ""
            bug_state = ""
            for bug in bug_list:
                if (test_case["className"] + "." + test_case["name"]) in bug[
                    "className"]:
                    bugno = bug["bugNo"]
                    bug_state = launchpad.bugs[bugno].bug_tasks[0].status
            if test_case['status'] == "REGRESSION":
                if bugno:
                    regressed_test_cases.append(
                        test_case["className"] + "." + test_case[
                            "name"] + '   -   unstable bug <a href="https://bugs.launchpad.net/tempest/+bug/{bugNo}">{bugNo}</a>'.format(
                            bugNo=bugno))
                else:
                    regressed_test_cases.append(
                        test_case["className"] + "." + test_case[
                            "name"] + '   -  under investigation')
            if test_case['status'] == "FIXED":
                if bugno:
                    fixed_test_cases.append(
                        test_case["className"] + "." + test_case[
                            "name"] + '   -   unstable bug <a href="https://bugs.launchpad.net/tempest/+bug/{bugNo}">{bugNo}</a>'.format(
                            bugNo=bugno))
                else:
                    fixed_test_cases.append(
                        test_case["className"] + "." + test_case[
                            "name"] + '   -  under investigation')
            if test_case['status'] == "REGRESSION" or test_case['status'] == "FAILED":
                failed_tests_amount += 1
                bug_status = "under investigation"
                if bugno:
                    bug_stats[bugno] = bug_stats.get(bugno, 0) + 1
                    bug_status = '<a href="https://bugs.launchpad.net/tempest/+bug/{bugNo}">{bugNo}</a>  -  {bug_state}'.format(
                        bugNo=bugno, bug_state=bug_state)
                failed_tests.append({"test_no": failed_tests_amount,
                                     "test": test_case["className"] + "." +
                                             test_case["name"],
                                     "bug_status": bug_status})
        if not failed_tests_amount:
            failed_tests.append({"test": "All Passed"})
        failed_tests_table[data[job]["name"]] = (
        {"name": data[job]["name"], "failed_tests": failed_tests,
         "fixed": fixed_test_cases, "regressed": regressed_test_cases})
    return failed_tests_table


def check_regression(data):
    empty_regression = {
        "failures_regression": "n/a",
        "passed_regression": "n/a",
        "skipped_regression": "n/a",
        "time_regression": "n/a",
        "total_regression": "n/a"
    }
    data["total"]["regress"] = {
        "failures_regression": {"pos": 0, "neg": 0},
        "passed_regression": {"pos": 0, "neg": 0},
        "skipped_regression": {"pos": 0, "neg": 0},
        "time_regression": {"pos": 0, "neg": 0},
        "total_regression": {"pos": 0, "neg": 0},
    }
    for topo in data:
        if 'prev_build_link' not in data[topo]:
            continue
        prev_link = data[topo]["prev_build_link"]
        try:
            result = json.loads(requests.get(prev_link).content)
            data[topo]["regress"] = {}
            data[topo]["regress"]["failures_regression"] = data[topo][
                                                               "failures_number"] - int(
                result['failCount'])
            data[topo]["regress"]["passed_regression"] = data[topo][
                                                             "passes_number"] - int(
                result['passCount'])
            data[topo]["regress"]["skipped_regression"] = data[topo][
                                                              "skipped_number"] - int(
                result['skipCount'])
            data[topo]["regress"]["time_regression"] = data[topo][
                                                           "time"] - float(
                result['duration'])
            data[topo]["regress"]["total_regression"] = data[topo][
                                                            "tests_number"] - sum(
                [int(i) for i in (
                result['passCount'], result['failCount'], result['skipCount'])])
            if data[topo]["regress"]["failures_regression"] > 0:
                data["total"]["regress"]["failures_regression"]["pos"] += \
                data[topo]["regress"]["failures_regression"]
            else:
                data["total"]["regress"]["failures_regression"]["neg"] -= \
                data[topo]["regress"]["failures_regression"]
            if data[topo]["regress"]["passed_regression"] > 0:
                data["total"]["regress"]["passed_regression"]["pos"] += \
                data[topo]["regress"]["passed_regression"]
            else:
                data["total"]["regress"]["passed_regression"]["neg"] -= \
                data[topo]["regress"]["passed_regression"]
            if data[topo]["regress"]["skipped_regression"] > 0:
                data["total"]["regress"]["skipped_regression"]["pos"] += \
                data[topo]["regress"]["skipped_regression"]
            else:
                data["total"]["regress"]["skipped_regression"]["neg"] -= \
                data[topo]["regress"]["skipped_regression"]
            if data[topo]["regress"]["total_regression"] > 0:
                data["total"]["regress"]["total_regression"]["pos"] += \
                data[topo]["regress"]["total_regression"]
            else:
                data["total"]["regress"]["total_regression"]["neg"] -= \
                data[topo]["regress"]["total_regression"]

            for reg in data[topo]["regress"]:
                number = data[topo]["regress"][reg]
                if number > 0:
                    data[topo]["regress"][reg] = "+" + str(number)
                else:
                    data[topo]["regress"][reg] = str(number)
        except Exception:
            data[topo]["regress"] = empty_regression
    return data


def process_current_builds():
    data = {}
    total = {"name": "Total Result", "failures_number": 0, "passes_number": 0,
             "skipped_number": 0, "tests_number": 0,
             "results_link": os.environ["JENKINS_URL"],
             "data_link": os.environ["JENKINS_URL"], "time_str": "n/a",
             "total_time_str": "n/a"}
    jobs = [v['job'] for v in TOPOS.itervalues()]
    for job in jobs:
        topo = next(iter([i for i in TOPOS if TOPOS[i]["job"] == job]), None)
        if not topo:
            raise Exception("Running jobs are inconsistent with configuration")
        current_job = os.environ["JENKINS_URL"] + "job/" + TOPOS[topo][
            "job"] + "/"
        current_build_no = str(
            json.loads(requests.get(current_job + "api/json").content)[
                "lastCompletedBuild"]["number"])
        if "TRIGGERED_BUILD_NUMBER_" + TOPOS[topo]["job"] in os.environ:
            current_build_no = os.environ[
                "TRIGGERED_BUILD_NUMBER_" + TOPOS[topo]["job"]]
        current_link = (
        current_job + current_build_no + "/testReport/api/json?pretty=true")
        current_build_link = (
        current_job + current_build_no + "/api/json?pretty=true")
        try:
            build_result = json.loads(requests.get(current_build_link).content)
        except Exception as e:
            print >> sys.stderr, "No current build from Jenkins API for %s : %s!" % (
                TOPOS[topo]["job"],
                os.environ["TRIGGERED_BUILD_NUMBER_" + TOPOS[topo]["job"]]
            )
            continue
        try:
            result = json.loads(requests.get(current_link).content)
            data[topo] = {'ok': True}
            data[topo].update({"name": TOPOS[topo]["name"]})
            data[topo].update({"failures_number": int(result['failCount'])})
            data[topo].update({"passes_number": int(result['passCount'])})
            data[topo].update({"time": float(result['duration'])})
            data[topo].update({"time_str": str_time(int(result['duration']))})
            data[topo].update(
                {"total_time": int(build_result['duration']) / 1000})
            data[topo].update({
            "total_time_str": str_time(int(build_result['duration']) / 1000)})
            data[topo].update({"skipped_number": int(result['skipCount'])})
            data[topo].update({"tests_number": sum(
                [int(i) for i in (
                result['passCount'], result['failCount'], result['skipCount'])]
            )})
            data[topo].update({
            "results_link": current_job + current_build_no + "/testReport/"})
            back_iter = 1
            while json.loads(requests.get(current_job + str(int(
                    current_build_no) - back_iter) + "/api/json?pretty=true").content)[
                "result"] == "FAILURE" and back_iter < 4:
                back_iter += 1
            data[topo].update({"prev_build_link": current_job + str(
                int(current_build_no) - back_iter) + "/testReport"
                                                     "/api/json?pretty=true"})
            data[topo].update({"data_link": LOG_SERVER_LOCATION + TOPOS[topo][
                "job"] + "/" + current_build_no})
            data[topo].update({
            "current_build_info": current_job + current_build_no + "/api/json?pretty=true"})
            total["failures_number"] += int(result['failCount'])
            total["passes_number"] += int(result['passCount'])
            total["skipped_number"] += int(result['skipCount'])
            total["tests_number"] += sum(
                [int(i) for i in (
                result['passCount'], result['failCount'], result['skipCount'])])

        except Exception as e:
            print >> sys.stderr, "No current results from Jenkins API for %s" % (
                TOPOS[topo]["job"]
            )
            data[topo] = {'ok': False}
            data[topo].update({"data_link": current_job})
            data[topo].update({"name": TOPOS[topo]["name"]})
            data[topo].update(
                {"total_time": int(build_result['duration']) / 1000})
            data[topo].update({
            "total_time_str": str_time(int(build_result['duration']) / 1000)})
    total_json = json.loads(requests.get(os.environ[
                                             "JENKINS_URL"] + "job/" + AGGREGATOR_JOB_NAME + "/lastCompletedBuild/api/json/").content)
    total["results_link"] = total_json["url"]
    total["total_time_str"] = str_time(int(total_json["duration"] / 1000))
    data["total"] = total
    return data


def pretty_report(data):
    topos_template = "\n{style}\n".format(style=STYLE)
    topos_template += table_row_template4.format(**data["total"])
    for topo in data:
        if 'results_link' in data[topo] and topo != "total":
            topos_template += table_row_template3.format(
                **data[topo])
        elif topo != "total":
            topos_template += failed_topo_template.format(
                **data[topo])

    main_template = main_template_demo.format(topos=topos_template)

    return main_template


def pretty_report_for_mail(data, bug_lists):
    main_template = """
    <script>
    </script>
    </br> Hi </br></br>

    <strong>Functional Product regression: <p style='color:green'>no regression</p></strong> </br>
    Today we had stable results. Failed tests were reran locally, all passed. </br>
    Investigated # failed tests. # bugs were created</br></br>
    Bug number ###### - affected # tests</br></br>

    <strong>Open bugs for new features:</strong>
    """
    for bug_stat, amount in bug_stats.iteritems():
        main_template += 'Bug # <a href="https://bugs.launchpad.net/tempest/+bug/{bugNo}">{bugNo}</a>  -  affected {amount} tests</br>\n'.format(bugNo=bug_stat, amount=amount)

    link_to_results = """<tr><a href="http://wikicentral.cisco.com/display/OPENSTACK/Nightly+testing"><strong>[Nightly Testing Details]</strong></a>
 </br> </br>"""
    main_template += link_to_results
    main_template += pretty_report(data)
    main_template += "</br><strong>Git Revisions</strong></br>"
    for name, repo in GITHUB_URLS.iteritems():
        request = requests.get(repo["api"])
        if request.status_code == 200:
            git_commit = json.loads(request.content)
            revision = git_commit["object"]["sha"]
        else:
            revision = 'unavailable'
        main_template += """
        <a href='{repo}/commit/{revision}'>{repo}</a></br> """.format(
            repo=repo["url"], revision=revision)

    for job in data:
        if job != "total":
            main_template += "<h4>" + data[job]["name"] + "</h4>\n"
            if 'results_link' in data[job]:
                bug_list = bug_lists[data[job]["name"]]
                if len(bug_list["regressed"]) or len(bug_list["fixed"]):
                    main_template += "<p style='color:green'>Fixed tests: </p>"
                    if len(bug_list["fixed"]):
                        for fixed in bug_list["fixed"]:
                            main_template += fixed + "</br>"
                    else:
                        main_template += "No changes</br>"
                    main_template += "<p style='color:red'>Regressed tests: </p>"
                    if len(bug_list["regressed"]):
                        for regressed in bug_list["regressed"]:
                            main_template += regressed + "</br>"
                    else:
                        main_template += "No changes</br>"
                else:
                    main_template += "<p style='color:green'><strong>No changes</strong></p>"
            else:
                main_template += "<p style='color:red'><strong>!!!!!FAILED TO TEST!!!!!</strong></p>"

    main_template += "</br><h2>Bug List</h2></br>"
    if bug_lists:
        for name, bug_list in bug_lists.iteritems():
            bug_table = ""
            for bug in bug_list["failed_tests"]:
                color = "blue"
                color2 = ""
                if bug.get("test", "") == "All Passed":
                    color2 = 'green'
                elif bug.get("bug_status", "") == "under investigation":
                    color = 'red'
                bug_table += table_row_bug_template.format(
                    testNo=bug.get("test_no", "  "),
                    testName=bug.get("test", " - "), color=color, color2=color2,
                    bugNo=bug.get("bug_status", " - "))
            if bug_list["failed_tests"][0]["test"] != "All Passed":
                main_template += table_bug_template.format(job=name,
                                                           rows=bug_table)
            else:
                main_template += table_bug_template2.format(job=name)
    return main_template


def main():
    try:
        config_file = sys.argv[1]
        with open(config_file) as f:
            config = yaml.load(f)
            global TOPOS
            TOPOS = config
    except Exception as e:
        print "Provide configuration file as argument!"
        raise e

    xml_report = process_current_builds()
    regression_report = check_regression(xml_report)
    if os.getenv("MAKE_BUG_LIST"):
        failed_tests_report = get_failed_tests(xml_report)
        print pretty_report_for_mail(regression_report, failed_tests_report)
    else:
        print pretty_report(regression_report)


if __name__ == '__main__':
    main()