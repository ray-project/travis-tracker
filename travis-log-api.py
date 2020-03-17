import datetime
import json
import time
import os
import re

import pytz
import redis
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

GH_ACCESS_TOKEN = os.environ["GH_TOKEN"]

HEADERS = {"Authorization": f"token {GH_ACCESS_TOKEN}", "Travis-API-Version": "3"}

BAZEL_STATUS = [
    "NO_STATUS",
    "PASSED",
    "FLAKY",
    "TIMEOUT",
    "FAILED",
    "INCOMPLETE",
    "REMOTE_FAILURE",
    "FAILED_TO_BUILD",
    "BLAZE_HALTED_BEFORE_TESTING",
]

reg = re.compile(
    r"""
    ^\/\/python\/ray
    ([^\s]+)
    \s+
    ({})
    .+$
""".format(
        "|".join(BAZEL_STATUS)
    ),
    re.VERBOSE | re.MULTILINE,
)
r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

pytest_sugar_map = {"✓": "PASSED", "⨯": "FAILED", "s": "SKIPPED"}

corrupted_jobs = {251667399}


def _cleanup_ascii_escape(bytes_content):
    # https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python

    ansi_escape = re.compile(
        r"""
        \x1B    # ESC
        [@-_]   # 7-bit C1 Fe
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    """.encode(),
        re.VERBOSE,
    )

    return re.sub(ansi_escape, b"", bytes_content).decode()


def _map_pytest_sugar_to_normal(pytest_result):
    cleaned_sugar_result = []
    for test_name, test_status in pytest_result:
        test_status = pytest_sugar_map.get(test_status, test_status)
        # sugar strip out python/
        if test_name.startswith("ray/"):
            test_name = "python/" + test_name
        # sugar change class based test from :: -> .
        # so we are going to normalize it and replace the fault positive .py back
        test_name = test_name.replace(".", "::").replace("::", ".", 1)
        cleaned_sugar_result.append((test_name, test_status))
    return cleaned_sugar_result


def get_master_branch_builds(limit=10):
    master_builds = requests.get(
        "https://api.travis-ci.com/repo/ray-project%2Fray"
        "/builds?build.event_type=push&branch.name=master"
        "&limit={}".format(limit),
        headers=HEADERS,
    ).json()
    return master_builds["builds"]


def build_info(build):
    return {
        "sha": build["commit"]["sha"][:6],
        "commit_message": build["commit"]["message"],
        "job_ids": [j["id"] for j in build["jobs"][:2]],
        "build_id": int(build["id"]),  # so they are sortable
    }


# TODO: Timeout this operation.
def fetch_test_status(job_id):
    if job_id in corrupted_jobs:
        return []

    resp = requests.get(
        f"https://api.travis-ci.com/job/{job_id}/log.txt", headers=HEADERS
    )
    if resp.status_code != 200:
        return []

    logs_txt = resp.content
    if logs_txt == "null" or len(logs_txt) < 100:
        return []

    out = _cleanup_ascii_escape(logs_txt)
    out = reg.findall(out)
    return _map_pytest_sugar_to_normal(out)


ONE_WEEK_SECONDS = 7 * 24 * 60 * 60

masters = get_master_branch_builds(limit=25)
for build in tqdm(masters):
    info = build_info(build)

    build_id = info["build_id"]
    r.sadd("build_ids", build_id)
    r.set(f"build/{build_id}", json.dumps(info))

    for job_id in info["job_ids"]:
        status = fetch_test_status(job_id)

        r.set(f"job/{job_id}", json.dumps(status))

# retrieve current pacific time
d = datetime.datetime.now()
timezone = pytz.timezone("America/Los_Angeles")
d_aware = timezone.localize(d)
r.set("last_updated", str(d_aware))
r.set("last_updated_unix", str(time.time()))
