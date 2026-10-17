# 实战样例：遗留代码的行为基线（Python，无测试）

演示工作流 2：面对没有测试的历史代码，先用「行为基线测试」锁定当前行为，再做结构化重构。流程说明见 references/workflows.md 工作流 2。

## 1. 遗留代码（无测试、行为隐晦）

```python
def calc(items, region, is_vip=False):
    t = 0
    for i in items:
        if i:
            q = i.get("qty") or 0
            p = i.get("price") or 0
            if q > 0:
                t += p * q
            if i.get("cat") == "book":
                t -= p * q * 0.1
    if t > 100:
        t = t * 0.98
    if region == "US":
        t += t * 0.08
    elif region == "EU":
        t += t * 0.2
    if is_vip:
        t -= 3
    return round(t, 2)
```

**为什么危险**：`items` 里可能混入 `None`；`i.get("qty") or 0` 把「0」与「缺失」混为一谈；`t -= p*q*0.1` 在 `q <= 0` 时仍会扣减（负数量时反而增加总价）；`is_vip` 减 3 可能把总价减成负数；四舍五入只发生在最后一步。这些都是「当前真实行为」，重构前必须先固定下来。

## 2. 第一步：生成行为基线测试（不改代码）

```text
为下面这段函数生成「行为基线测试」，目标是如实捕捉它当前的真实行为（即使看起来像 bug 也照原样断言），不要修正行为、不要改被测代码。

- 覆盖：正常路径、空输入、items 含 None、数量为 0 / 负数 / 缺失、book 与非 book、region 为 US / EU / 其他、VIP 与非 VIP、总价恰好 100；
- 断言要具体（给定输入 → 期望输出，包含浮点结果）；
- 测试必须在当前代码上直接通过。
{粘贴上面的 calc 函数}
```

生成的基线用例（节选，pytest；期望值是**在当前实现上实际跑出来的**，不是手算的理想值）：

```python
import pytest
from legacy import calc

@pytest.mark.parametrize("items, region, is_vip, expected", [
    ([], "US", False, 0.0),
    ([None], "US", False, 0.0),
    ([{"qty": 2, "price": 50, "cat": "book"}], "US", False, 97.2),
    ([{"qty": 0, "price": 50, "cat": "book"}], "US", False, 0.0),
    ([{"qty": 2, "price": 50}], "US", False, 108.0),
    ([{"qty": 3, "price": 40, "cat": "book"}], "US", True, 111.31),
])
def test_calc_baseline(items, region, is_vip, expected):
    assert calc(items, region, is_vip) == expected
```

> 注意第二条与第五条：空列表与「总价恰好 100」都不触发满减（判断是 `> 100` 而非 `>= 100`），这正是必须被锁死的边界。

## 3. 第二步：重构（套用主模板）

```text
你是资深 Python 工程师，专注在不改变行为的前提下做重构。

【硬约束】
1. 第 2 步的行为基线测试必须原样通过，一条都不许改；
2. 不改变函数签名 calc(items, region, is_vip=False) 与返回值语义；
3. 现有隐式行为（None 项、qty <= 0、负数总价、舍入时机）必须保留，并在代码注释中显式标注。

【重构目标】
1. 拆分：解析条目 / 分类折扣 / 订单折扣 / 税费 / VIP 调整，各自单一职责；
2. 用具名常量替换魔法数字；
3. 保持计算顺序与舍入时机不变。

【验收标准】
测试命令：pytest（含全部行为基线测试）必须通过。
```

## 4. 参考重构结果

```python
BOOK_DISCOUNT = 0.1
ORDER_THRESHOLD = 100
ORDER_DISCOUNT = 0.02
TAX_RATES = {"US": 0.08, "EU": 0.2}
VIP_ADJUSTMENT = 3


def calc(items, region, is_vip=False):
    total = _subtotal(items)
    if total > ORDER_THRESHOLD:
        total *= 1 - ORDER_DISCOUNT
    total += total * TAX_RATES.get(region, 0)
    if is_vip:
        total -= VIP_ADJUSTMENT
    return round(total, 2)


def _subtotal(items):
    total = 0.0
    for item in items:
        if not item:                    # 原行为：None / 空 dict 视为无条目
            continue
        qty = item.get("qty") or 0
        price = item.get("price") or 0
        if qty > 0:
            total += price * qty
        if item.get("cat") == "book":
            total -= price * qty * BOOK_DISCOUNT   # 原实现对 qty<=0 也无条件扣减，保留
    return total
```

## 5. 这个流程为什么可靠

- **行为先固定，再动结构**：基线测试是唯一能证明「行为等价」的证据，空泛的「保持行为不变」不可验收。
- **隐式行为被显式标注**：`qty <= 0` 时的异常扣减被保留并加注释，而不是被顺手「修好」——那属于行为变更，应另开变更单。
- **重构后如有用例必须修改，说明发生了行为变化**：此时应停下来确认，而不是改测试迁就代码。
