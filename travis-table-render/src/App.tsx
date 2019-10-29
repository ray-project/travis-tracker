import { Icon, Table, Col, Row, Tooltip, Spin, Typography } from "antd";
import { useState } from "react";
import React from "react";
import "./App.css";
import { ReactComponent as LinuxIcon } from "./icons/linux.svg";
import { ReactComponent as PythonIcon } from "./icons/python.svg";
import moment from "moment";
import _ from "underscore";

import axios from "axios";

const GreenCheck = <Icon type="check" style={{ color: "green" }} />;
const RedClosed = <Icon type="close" style={{ color: "red" }} />;
const GreyQuestionMark = <Icon type="question" />;
const GreyRightArrow = <Icon type="right" />;

function trimRowName(name: string) {
  let splitArray = name.split("/");
  let trimmedName = splitArray[splitArray.length - 1];

  return (
    <Tooltip title={name}>
      <Typography.Text style={{ width: "300px" }} ellipsis>
        {trimmedName}
      </Typography.Text>
    </Tooltip>
  );
}

function renderTable(table: JSX.Element, lastUpdated: number) {
  return (
    <div>
      <Col span={20} offset={2}>
        <h1>Ray Project Travis Status Tracker</h1>

        <Row>
          <Col span={6} offset={2}>
            Icon Legend:
            <ul>
              <li>{GreenCheck} : Passed </li>
              <li>{RedClosed} : Failed </li>
              <li>{GreyRightArrow} : Skipped </li>
              <li>{GreyQuestionMark} : Unknown </li>
            </ul>
          </Col>

          <Col span={6} offset={2}>
            Icon Ordering:
            <ol>
              <li>
                <LinuxIcon />, <PythonIcon /> 2{" "}
              </li>
              <li>
                <LinuxIcon />, <PythonIcon /> 3{" "}
              </li>
              <li>
                <Icon type="apple" />, <PythonIcon /> 2{" "}
              </li>
              <li>
                <Icon type="apple" />, <PythonIcon /> 3{" "}
              </li>
            </ol>
          </Col>

          {lastUpdated === 0 ? (
            ""
          ) : (
            <Col span={4} offset={-4}>
              {/* Seems like python vs js inconsistency */}
              {/* time.time() returns float unix timestamp in seconds */}
              {/* here it must be multiplied by 1000 */}
              Last updated:
              <li>{moment(lastUpdated * 1000).fromNow()}</li>
            </Col>
          )}
        </Row>

        {table}
      </Col>
    </div>
  );
}

// const DEV_SERVER = "http://127.0.0.1:5000";
const DEV_SERVER = "";

const InnerApp: React.FC = () => {
  let [rawData, setRawData] = useState<any>();
  let [lastUpdated, setLastUpdated] = useState<number>(0);

  if (rawData === undefined) {
    axios
      .get(`${DEV_SERVER}/last_updated`)
      .then(function(response) {
        console.log(`Last updated at (Pacific Time) ${response.data}`);
        setLastUpdated(Number(response.data));
      })
      .catch(function(error) {
        console.log("Pinging /last_updated failed");
        console.log(error);
      });

    axios
      .get(`${DEV_SERVER}/api`)
      .then(function(response) {
        // handle success
        setRawData(response.data);
      })
      .catch(function(error) {
        console.log("Pinging /api failed");
        console.log(error);
      });

    return renderTable(
      <Col span={12} offset={6}>
        <Spin size="large" />
        <p>Loading...</p>
        <p>If it is loading for too long, please file an issue at</p>
        <p>
          <a href="https://github.com/ray-project/travis-tracker/issues/new">
            ray-project/travis-tracker repo
          </a>
        </p>
      </Col>,
      lastUpdated
    );
  }

  let sortedColumnName: number[] = _.uniq(
    rawData.columns.map((build_id: string[]) => Number(build_id[0]))
  );

  let data: Array<any> = [];
  // {key:..., name:..., col1: status, ...}
  let keyCounter = 0;
  for (let item of _.zip(rawData.index, rawData.data)) {
    let idx: string;
    let row: string[];
    [idx, row] = item;

    let failedCount = 0;
    const transformTestStatus = (testStatus: number) => {
      //   "encoding": {
      //     "PASSED": 0,
      //     "FAILED": 1,
      //     "SKIPPED": 2,
      //     "UNKNOWN": 3
      // }
      if (testStatus === 0) {
        return GreenCheck;
      } else if (testStatus === 1) {
        failedCount += 1;
        return RedClosed;
      } else if (testStatus === 2) {
        return GreyRightArrow;
      } else {
        return GreyQuestionMark;
      }
    };

    let commitStatus: { [k: string]: any } = {};
    for (let group of _.zip(sortedColumnName, _.chunk(row, 4) as string[][])) {
      let [colName, statusGroup] = group;
      commitStatus[colName] = (
        <Typography.Text>
          {statusGroup.map(transformTestStatus)}
        </Typography.Text>
      );
    }

    data.push({
      key: keyCounter,
      name: trimRowName(idx),
      failedCount: failedCount,
      ...commitStatus
    });
    keyCounter += 1;
  }

  function formatColumnName(buildId: number) {
    let metadata = (rawData["metadata"] as any)[buildId.toString()];
    let sha = metadata.sha;

    let toolTipNode = (
      <div>
        <p>Commit: {metadata["commit_message"].split("\n")[0]}</p>
        <p>
          <a href={"https://travis-ci.com/ray-project/ray/builds/" + buildId}>
            Go to Travis
          </a>
        </p>
      </div>
    );

    return (
      <Tooltip title={toolTipNode}>
        <Typography.Text underline>{sha} </Typography.Text>
      </Tooltip>
    );
  }

  let columns: Array<any> = [
    {
      title: "Test Name",
      dataIndex: "name",
      fixed: "left",
      width: 100
    },
    {
      title: (
        <Tooltip title="Number of failed tests across past 10 commits">
          <span># Failed</span>
        </Tooltip>
      ),
      dataIndex: "failedCount",
      fixed: "left",
      width: 50
    },
    ...sortedColumnName.map((name: number) => {
      return {
        title: formatColumnName(name),
        dataIndex: name,
        width: 100
      };
    })
  ];

  return renderTable(
    <Table
      columns={columns}
      dataSource={data}
      // pagination={false}
      scroll={{ x: 2700 }}
    />,
    lastUpdated
  );
};

// // Profiling Used
// const App:React.FC = () => {
//   let [visible, setVisible] = useState(false)

//   return <div>
//     {visible ? <InnerApp/> : <Button onClick={(event)=>setVisible(true)}>Render</Button>}
//   </div>
// }

const App = InnerApp;

export default App;
