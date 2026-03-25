import test from "node:test";
import assert from "node:assert/strict";

import { shouldShowStageStatus } from "../src/lib/stageStatusVisibility.ts";

test("完成后不再显示阶段状态标签", () => {
  assert.equal(
    shouldShowStageStatus({
      current: "正在生成代码...",
      history: ["开始生成", "正在生成代码..."],
      isComplete: true,
    }),
    false
  );
});

test("执行中有当前阶段时显示阶段状态标签", () => {
  assert.equal(
    shouldShowStageStatus({
      current: "正在生成代码...",
      history: [],
      isComplete: false,
    }),
    true
  );
});
