# 实战样例：遗留 TypeScript 代码的行为基线（无测试）

演示工作流 2 + 工作流 4：老 TS/JS 代码常见「全 `any` + 宽松真值判断 + 浮点四舍五入」，先用行为基线测试锁住当前行为，再补类型、抽常量、拆函数，最后用差分测试证明运行时行为完全一致（类型只是编译期收益）。

代码块带 `<!-- verify:file=... -->` 标记，CI 会用 .github/scripts/verify_examples.py 在 Node 24 下实际执行 `node --test`。

<!-- verify:run
node --test baseline.test.ts differential.test.ts
-->

## 1. 遗留代码（any 满天飞、行为隐晦）

<!-- verify:file=legacy.ts -->
```ts
export function total(order: any): number {
  let t = 0;
  for (const i of order.items) {
    if (!i) continue;
    const q = i.qty || 0;
    const p = i.price || 0;
    if (q > 0) t += p * q;
    if (i.cat === 'book') t -= p * q * 0.1;
  }
  if (t > 100) t = t * 0.98;
  if (order.region === 'US') t += t * 0.08;
  else if (order.region === 'EU') t += t * 0.2;
  if (order.vip) t -= 3;
  return Math.round(t * 100) / 100;
}
```

**为什么危险**：`any` 让字段拼错也不报错；`i.qty || 0` 把 `0`、`NaN`、缺失混为一谈；`i.cat === 'book'` 在 `q <= 0` 时仍无条件扣减（负数量反而加价）；`Math.round(t * 100) / 100` 的浮点截断点非常敏感；`order.items` 缺失时直接抛错。这些隐式行为必须先固定。

## 2. 第一步：行为基线测试（先跑通，不改代码）

```text
为下面的 TypeScript 函数生成「行为基线测试」，目标是捕捉当前真实行为（即使看起来像 bug 也照原样断言），不要修改被测代码。

- 覆盖：空数组、null 项、qty 为 0 / 负数 / 缺失、book 与非 book、总价恰好 100、US / EU / 其他地区、VIP；
- 断言具体到两位小数的数值（含 Math.round 的截断结果）；
- 测试必须在当前代码上直接通过。
{粘贴上面的 legacy.ts}
```

生成的基线测试（`node --test` 通过）：

<!-- verify:file=baseline.test.ts -->
```ts
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { total } from './legacy.ts';

const cases: Array<[string, any, string, boolean, number]> = [
  ['empty order', [], '', false, 0],
  ['null item ignored', [null], '', false, 0],
  ['book discount', [{ qty: 2, price: 50, cat: 'book' }], 'US', false, 97.2],
  ['disabled qty still deducts book discount', [{ qty: 0, price: 50, cat: 'book' }], '', false, 0],
  ['negative qty book increases total', [{ qty: -1, price: 100, cat: 'book' }], '', false, 10],
  ['no order discount at exactly 100', [{ qty: 1, price: 100 }], '', false, 100],
  ['us tax', [{ qty: 2, price: 50 }], 'US', false, 108],
  ['vip goes negative', [{ qty: 3, price: 40, cat: 'book' }], 'US', true, 111.31],
];

test('baseline: current behaviour is locked', () => {
  for (const [name, items, region, vip, expected] of cases) {
    assert.equal(total({ items, region, vip }), expected, name);
  }
});
```

> 第三条与第五条说明：`q <= 0` 时 book 折扣仍被无条件扣减；「总价恰好 100」不触发满减（`> 100` 而非 `>= 100`）。期望值必须来自实际执行。

## 3. 第二步：重构（套用主模板）

```text
你是资深 TypeScript 工程师，专注在不改变行为的前提下做重构。

【硬约束】
1. 第 2 步的行为基线测试必须原样通过，一条都不许改；
2. 不改变运行时行为：浮点运算顺序、Math.round 截断点、隐式真值判断的边界都必须一致；
3. 不新增第三方依赖；只允许补类型，不允许改变函数签名语义（入参形状兼容）。

【重构目标】
1. 用 interface 替换 any，字段可选性与原访问方式兼容；
2. 用具名常量替换魔法数字（折扣、阈值、税率、VIP 调整）；
3. 把条目小计、订单折扣、税费、VIP 调整拆成单一职责函数；保留原隐式行为并加注释。

【验收标准】
测试命令：node --test（含全部行为基线测试）必须通过。
```

## 4. 参考重构结果

<!-- verify:file=refactored.ts -->
```ts
export interface Item {
  qty?: number;
  price?: number;
  cat?: string;
}

export interface Order {
  items: Array<Item | null>;
  region?: string;
  vip?: boolean;
}

const BOOK_DISCOUNT = 0.1;
const ORDER_THRESHOLD = 100;
const ORDER_DISCOUNT_RATE = 0.98;
const TAX_RATES: Record<string, number> = { US: 0.08, EU: 0.2 };
const VIP_ADJUSTMENT = 3;

export function total(order: Order): number {
  let t = subtotal(order.items);
  if (t > ORDER_THRESHOLD) t *= ORDER_DISCOUNT_RATE;
  t += t * (TAX_RATES[order.region ?? ''] ?? 0);
  if (order.vip) t -= VIP_ADJUSTMENT;
  return Math.round(t * 100) / 100;
}

function subtotal(items: Array<Item | null>): number {
  let t = 0;
  for (const i of items) {
    if (!i) continue;
    const q = i.qty || 0;
    const p = i.price || 0;
    if (q > 0) t += p * q;
    if (i.cat === 'book') t -= p * q * BOOK_DISCOUNT;
  }
  return t;
}
```

注意 `ORDER_DISCOUNT_RATE = 0.98` 直接复用原字面量、`Math.round` 留在同一步、`|| 0` 与 `?? ''` 的语义分界保持原样：这些都是「看起来等价」的改写最容易破坏的浮点与真值边界。

## 5. 第三步：差分测试再兜一层

<!-- verify:file=differential.test.ts -->
```ts
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { total as legacyTotal } from './legacy.ts';
import type { Order } from './refactored.ts';
import { total as refactoredTotal } from './refactored.ts';

const cases: Order[] = [
  { items: [], region: '', vip: false },
  { items: [null], region: 'US', vip: false },
  { items: [{ qty: 3, price: 4000, cat: 'book' }], region: 'EU', vip: false },
  { items: [{ qty: 1, price: 100, cat: 'book' }], region: '', vip: true },
  {
    items: [
      { qty: 7, price: 333, cat: 'book' },
      { qty: 2, price: 1999, cat: 'electronics' },
    ],
    region: 'EU',
    vip: true,
  },
  { items: [{ qty: 1, price: 10001 }], region: 'US', vip: false },
  { items: [{ qty: 5, price: 2001, cat: 'electronics' }], region: 'US', vip: true },
];

test('refactored matches legacy on every case', () => {
  for (const [index, order] of cases.entries()) {
    assert.equal(refactoredTotal(order), legacyTotal(order), 'case ' + index);
  }
});

test('refactored matches legacy on generated cases', () => {
  let seed = 7;
  const rand = (bound: number): number => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed % bound;
  };
  const prices = [10, 40, 50, 99, 100, 333];
  const categories = ['book', 'electronics', 'other'];
  const regions = ['US', 'EU', ''];

  for (let index = 0; index < 300; index += 1) {
    const items: Order['items'] = [];
    for (let count = rand(5); count > 0; count -= 1) {
      items.push({
        qty: rand(8) - 2,
        price: prices[rand(prices.length)],
        cat: categories[rand(categories.length)],
      });
    }
    const order: Order = { items, region: regions[rand(regions.length)], vip: rand(3) === 0 };
    assert.equal(refactoredTotal(order), legacyTotal(order), 'generated case ' + index);
  }
});
```

## 6. 可执行验证

四个文件（`legacy.ts`、`baseline.test.ts`、`refactored.ts`、`differential.test.ts`）由 Node 原生 TypeScript 类型剥离直接执行，无需构建步骤。CI 用 `python3 .github/scripts/verify_examples.py --require-all` 写入临时目录（自动补 `package.json`，`type: module`）并执行 `node --test`；本地可 `--only typescript-legacy-characterisation` 单独跑。

## 7. 这个流程为什么可靠

- **运行时行为先固定**：类型只能保证编译期，行为等价仍靠基线测试与差分测试。
- **隐式真值判断被保留**：`|| 0`、`??`、`Math.round` 的边界没有在重构中「顺手优化」，避免把重构变成行为变更。
- **类型与行为解耦**：补 `interface` 是纯编译期收益，测试证明运行时零差异。
- **要改行为就单独提**：例如把 `|| 0` 改成严格校验，属于行为变更，应另开变更单并同步改测试。
