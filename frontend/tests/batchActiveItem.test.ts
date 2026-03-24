import test from "node:test";
import assert from "node:assert/strict";

import {
  pickActiveItemOnDone,
  pickActiveItemOnStart,
} from "../src/lib/batchActiveItem.ts";

test("启动新资产时，不打断当前等待选图的资产", () => {
  const next = pickActiveItemOnStart("card_a", {
    card_a: { status: "awaiting_selection" },
    relic_b: { status: "img_generating" },
  }, "relic_b");

  assert.equal(next, "card_a");
});

test("当前资产已完成时，启动新资产会切换焦点", () => {
  const next = pickActiveItemOnStart("card_a", {
    card_a: { status: "done" },
    relic_b: { status: "img_generating" },
  }, "relic_b");

  assert.equal(next, "relic_b");
});

test("当前资产完成后，自动切到下一个需要关注的资产", () => {
  const next = pickActiveItemOnDone("card_a", "card_a", {
    card_a: { status: "done" },
    relic_b: { status: "awaiting_selection" },
    power_c: { status: "pending" },
  });

  assert.equal(next, "relic_b");
});
