import json
import os

import pandas as pd
import redis
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

app = Flask(__name__, static_url_path="/", static_folder="static")
CORS(app)

r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

COMMITS_LIMIT_NUM = 25

@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/last_updated")
def last_updated():
    last_updated_unix = r.get('last_updated_unix')
    if last_updated_unix:
        return last_updated_unix
    return r.get("last_updated")


@app.route("/api")
def serve_table():
    _, build_ids = r.sscan("build_ids")
    sorted_build_ids = list(reversed([int(i) for i in build_ids]))[:COMMITS_LIMIT_NUM]

    build_infos = [json.loads(r.get(f"build/{i}")) for i in sorted_build_ids]
    assert len(build_infos), "Redis shouldn't be empty!"

    data = []
    for info in build_infos:
        for i, job_id in enumerate(info["job_ids"]):
            status = json.loads(r.get(f"job/{job_id}"))
            for test, result in status:
                data.append(
                    {
                        "test_name": test,
                        "result": result,
                        "job_sequence_number": i,
                        "build_id": int(info["build_id"]),
                    }
                )

    df = pd.DataFrame(data)
    df = df.groupby(["test_name", "job_sequence_number", "build_id"]).first().unstack()
    df.columns = df.columns.droplevel()
    df = df.loc[:, sorted_build_ids].unstack().fillna("UNKNOWN")

    score_df = df.replace(
        {"FAILED": 10.0, "UNKNOWN": 0.1, "SKIPPED": 0.0, "PASSED": 0.0}
    )

    sorted_scores = score_df.sum(axis=1).sort_values(ascending=False)
    encoding_dict = {"PASSED": 0, "FAILED": 1, "SKIPPED": 2, "UNKNOWN": 3}
    ranked_df = df.loc[sorted_scores.index].replace(encoding_dict)

    json_data = ranked_df.to_dict(orient="split")
    build_meta_data = {b["build_id"]: b for b in build_infos}
    json_data["metadata"] = build_meta_data
    json_data["encoding"] = encoding_dict

    return jsonify(json_data)
