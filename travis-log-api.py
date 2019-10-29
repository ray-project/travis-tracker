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
reg = re.compile(
    r"""
    ^\s* # whitespace
    ray/ # all test anme should begin with ray directory
    (.+::[^\s]+) # test name
    .*
    (PASSED|FAILED|SKIPPED|✓|⨯|s)
    .+
""",
    re.VERBOSE | re.MULTILINE,
)
r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

pytest_sugar_map = {"✓": "PASSED", "⨯": "FAILED", "s": "SKIPPED"}


def _cleanup_ascii_escape(texts):
    # https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python

    ansi_escape = re.compile(
        r"""
        \x1B    # ESC
        [@-_]   # 7-bit C1 Fe
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    """,
        re.VERBOSE,
    )

    return re.sub(ansi_escape, "", texts)


def _map_pytest_sugar_to_normal(pytest_result):
    cleaned_sugar_result = []
    for test_name, status in pytest_result:
        status = pytest_sugar_map.get(status, status)
        cleaned_sugar_result.append((test_name, status))
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
        "job_ids": [j["id"] for j in build["jobs"][:4]],
        "build_id": int(build["id"]),  # so they are sortable
    }


def fetch_test_status(job_id):
    logs_txt = requests.get(
        f"https://api.travis-ci.com/job/{job_id}/log.txt", headers=HEADERS
    ).text
    if logs_txt == "null" or len(logs_txt) < 100:
        return []
    else:
        return _map_pytest_sugar_to_normal(reg.findall(_cleanup_ascii_escape(logs_txt)))


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
