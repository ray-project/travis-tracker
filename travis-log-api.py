import datetime
import json
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
    """
^python/ray/tests/(.+::[^\s]+).*(PASSED|FAILED|SKIPPED).+
""",
    re.MULTILINE | re.VERBOSE,
)
r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


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
        return reg.findall(logs_txt)


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
