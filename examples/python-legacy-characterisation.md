# 实战样例：遗留代码的行为基线（Python，无测试）

演示工作流 2：面对没有测试的历史代码，先用「行为基线测试」锁定当前行为，再做结构化重构，最后用差分测试证明等价。流程说明见 references/workflows.md 工作流 2。

本样例的代码块带 `<!-- verify:file=... -->` 标记，CI 会用 .github/scripts/verify_examples.py 实际执行 `python -m unittest`；样例跑不过 CI 就红。

<!-- verify:run
python -m unittest discover -s . -p "test_*.py" -q
-->

## 1. 遗留代码（无测试、行为隐晦）

<!-- verify:file=legacy.py -->
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

生成的基线用例（标准库 unittest，零依赖；期望值是**在当前实现上实际跑出来的**，不是手算的理想值）：

<!-- verify:file=test_legacy.py -->
```python
import unittest

from legacy import calc


class BaselineTest(unittest.TestCase):
    CASES = [
        # items, region, is_vip, expected
        ([], "US", False, 0.0),
        ([None], "US", False, 0.0),
        ([{"qty": 2, "price": 50, "cat": "book"}], "US", False, 97.2),
        ([{"qty": 0, "price": 50, "cat": "book"}], "", False, 0.0),
        ([{"qty": -1, "price": 100, "cat": "book"}], "", False, 10.0),
        ([{"qty": 1, "price": 100}], "", False, 100.0),
        ([{"qty": 2, "price": 50}], "US", False, 108.0),
        ([{"qty": 3, "price": 40, "cat": "book"}], "US", True, 111.31),
    ]

    def test_baseline(self):
        for items, region, is_vip, expected in self.CASES:
            with self.subTest(items=items, region=region, is_vip=is_vip):
                self.assertEqual(calc(items, region, is_vip), expected)


if __name__ == "__main__":
    unittest.main()
```

> 注意第三条与第六条：数量为 0 或负数时 book 折扣仍被无条件扣减（反倒加价），而「总价恰好 100」不触发满减（判断是 `> 100` 而非 `>= 100`）——这些隐式边界必须被锁死。

## 3. 第二步：重构（套用主模板）

```text
你是资深 Python 工程师，专注在不改变行为的前提下做重构。

【硬约束】
1. 第 2 步的行为基线测试必须原样通过，一条都不许改；
2. 不改变函数签名 calc(items, region, is_vip=False) 与返回值语义；
3. 现有隐式行为（None 项、qty <= 0 的折扣、负数总价、舍入时机）必须保留，并在代码注释中显式标注。

【重构目标】
1. 拆分：解析条目 / 分类折扣 / 订单折扣 / 税费 / VIP 调整，各自单一职责；
2. 用具名常量替换魔法数字；
3. 保持计算顺序与舍入时机不变。

【验收标准】
测试命令：python -m unittest discover -s . -p "test_*.py"（含全部行为基线测试）必须通过。
```

## 4. 参考重构结果

<!-- verify:file=legacy_refactored.py -->
```python
BOOK_DISCOUNT = 0.1
ORDER_THRESHOLD = 100
ORDER_DISCOUNT_RATE = 0.98
TAX_RATES = {"US": 0.08, "EU": 0.2}
VIP_ADJUSTMENT = 3


def calc(items, region, is_vip=False):
    total = _subtotal(items)
    if total > ORDER_THRESHOLD:
        total *= ORDER_DISCOUNT_RATE
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

注意 `total *= ORDER_DISCOUNT_RATE` 里的常量就取 `0.98`：与原实现保持完全相同的浮点运算序列，否则「看起来一样」的改写可能在小数末位产生差异。

## 5. 第三步：差分测试（覆盖枚举用例之外）

<!-- verify:file=test_equivalence.py -->
```python
import random
import unittest

from legacy import calc
from legacy_refactored import calc as calc_refactored


class EquivalenceTest(unittest.TestCase):
    CASES = [
        ([], "US", False),
        ([None], "US", False),
        ([{"qty": 3, "price": 4000, "cat": "book"}], "EU", False),
        ([{"qty": 1, "price": 100, "cat": "book"}], "", True),
        ([{"qty": 7, "price": 333, "cat": "book"}, {"qty": 2, "price": 1999, "cat": "electronics"}], "EU", True),
        ([{"qty": 1, "price": 10001}], "US", False),
    ]

    def test_equivalence(self):
        for items, region, is_vip in self.CASES:
            with self.subTest(items=items, region=region, is_vip=is_vip):
                self.assertEqual(
                    calc(items, region, is_vip),
                    calc_refactored(items, region, is_vip),
                )

    def test_generated_equivalence(self):
        rng = random.Random(7)
        for _ in range(300):
            items = [
                {
                    "qty": rng.randint(-2, 5),
                    "price": rng.choice([10, 40, 50, 99, 100, 333]),
                    "cat": rng.choice(["book", "electronics", "other"]),
                }
                for _ in range(rng.randint(0, 4))
            ]
            region = rng.choice(["US", "EU", ""])
            is_vip = rng.random() < 0.3
            self.assertEqual(
                calc(items, region, is_vip),
                calc_refactored(items, region, is_vip),
                msg=f"items={items} region={region} vip={is_vip}",
            )


if __name__ == "__main__":
    unittest.main()
```

## 6. 可执行验证

四个文件把「遗留代码 → 基线测试 → 重构代码 → 差分测试」串成可执行链路。CI 用 `python3 .github/scripts/verify_examples.py --require-all` 在临时目录里执行 `python -m unittest discover -s . -p "test_*.py" -q`；本地可 `--only python-legacy-characterisation` 单独跑。

## 7. 这个流程为什么可靠

- **行为先固定，再动结构**：基线测试是唯一能证明「行为等价」的证据，空泛的「保持行为不变」不可验收。
- **隐式行为被显式标注**：`qty <= 0` 时的异常折扣被保留并加注释，而不是被顺手「修好」——那属于行为变更，应另开变更单。
- **差分测试扩覆盖**：枚举用例之外，再用固定种子的生成用例对比新旧实现，且浮点运算序列保持一致。
- **重构后如有用例必须修改，说明发生了行为变化**：此时应停下来确认，而不是改测试迁就代码。
