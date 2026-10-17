# 实战样例：遗留 SQL 的结果集等价改写（可执行验证）

演示「SQL 重构」的特殊难点：SQL 没有单元测试框架的默认答案，**验收标准只能是结果集**。先用固定数据集把当前查询的输出锁成基线（golden），再把嵌套子查询/相关子查询改写成 CTE + 聚合，最后逐行对比两个查询的结果。

代码块带 `<!-- verify:file=... -->` 标记，CI 会用 .github/scripts/verify_examples.py 调用 Python 标准库 `sqlite3` 实际执行 `python verify.py`——不需要任何第三方依赖。

<!-- verify:run
python verify.py
-->

## 1. 遗留查询（能跑，但行为隐晦）

<!-- verify:file=legacy.sql -->
```sql
SELECT c.name AS customer,
       IFNULL(SUM(o.total_cents), 0) AS revenue_cents,
       COUNT(o.id) AS order_count,
       (SELECT COUNT(*) FROM orders p
         WHERE p.customer_id = c.id AND p.status = 'paid') AS paid_count
FROM customers c
LEFT JOIN orders o
       ON o.customer_id = c.id
      AND o.status <> 'canceled'
GROUP BY c.id, c.name
ORDER BY revenue_cents DESC, c.name ASC;
```

**为什么危险**：这条查询的正确性藏在四个隐式约定里——`status <> 'canceled'` 对 `NULL` 状态不成立（NULL 比较结果为 NULL，被 JOIN 排除）；`COUNT(o.id)` 不数 NULL（无订单客户计 0）；`GROUP BY` 只按 id+name、却 SELECT 了 `name`（SQLite 允许，标准 SQL 会拒绝）；排序在主键相同时依赖 `name` 兜底。它们都没有写在需求里，改写时任何一处「顺手优化」都会改变结果集。

## 2. 数据集（让结果可复现）

<!-- verify:file=schema.sql -->
```sql
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT,
    total_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
```

<!-- verify:file=seed.sql -->
```sql
INSERT INTO customers (id, name, region, created_at) VALUES
    (1, 'Alice', 'US', '2023-01-01'),
    (2, 'Bob', 'EU', '2023-02-01'),
    (3, 'Carol', NULL, '2023-03-01'),
    (4, 'Dave', 'US', '2023-04-01'),
    (5, 'Eve', 'US', '2023-05-01');

INSERT INTO orders (id, customer_id, status, total_cents, created_at) VALUES
    (101, 1, 'paid', 5000, '2023-01-10'),
    (102, 1, 'paid', 2500, '2023-02-10'),
    (103, 1, 'canceled', 9999, '2023-02-15'),
    (104, 2, 'paid', 3000, '2023-03-01'),
    (105, 2, NULL, 700, '2023-03-02'),
    (106, 3, 'paid', 0, '2023-03-03'),
    (107, 3, 'refunded', 1200, '2023-03-04'),
    (108, 5, 'paid', 8000, '2023-04-01'),
    (109, 5, 'pending', 500, '2023-04-02');
```

数据集刻意包含：无订单客户（Dave）、`NULL` 状态订单（Bob 的 105）、取消订单（Alice 的 103）、0 元订单（Carol 的 106）、没有 `region` 的客户——都是改写时最容易踩的边界。

## 3. 第一步：先锁结果集基线

```text
为下面这条 SQL 生成「结果集基线」：在给定数据集上实际执行，把返回的每一行原样记录下来作为 golden（不要手算、不要"修正"结果），并说明每个隐式行为（NULL 比较、COUNT 语义、GROUP BY 选取、排序兜底）。

- 固定数据集：见 schema.sql + seed.sql（附上）；
- golden 必须包含：客户名、revenue_cents、order_count、paid_count，按查询自身排序；
- 同时说明哪些行证明了哪条隐式行为。
{粘贴 legacy.sql、schema.sql、seed.sql}
```

> golden 必须是**跑出来的**：手算很容易把 `NULL` 状态订单算进 Bob 的 revenue（实际被 `<> 'canceled'` 排除），这类错误正是基线要防的。

## 4. 第二步：重构（套用主模板）

```text
你是资深 SQL 工程师，专注在不改变结果集的前提下重写查询。

【硬约束】
1. 结果集必须逐行一致：行数、每列的值、排序都不得改变；
2. NULL 语义保持不变（尤其 status 为 NULL 的订单仍被排除在 revenue / order_count 之外）；
3. 不改变表结构、不新增索引、不引入方言特性；保持 SQLite 兼容；
4. 输出必须可读：用 CTE 表达中间步骤，避免重复子查询。

【重构目标】
1. 把相关子查询（paid_count）改为独立聚合后 LEFT JOIN，消除逐行扫描；
2. 用 CTE 命名中间结果（joined / paid），让每个聚合语义可单独阅读；
3. 显式保留分组键与排序兜底。

【验收标准】
- 测试命令：python verify.py
- 用例：基线 golden 逐行相等；重构查询与遗留查询结果集逐行相等
- 若无法执行：给出两个查询在同一数据集上的结果对照表（含 NULL 状态订单的处理）
```

## 5. 参考重构结果

<!-- verify:file=refactored.sql -->
```sql
WITH joined AS (
    SELECT c.id,
           c.name,
           o.id AS order_id,
           o.total_cents
    FROM customers c
    LEFT JOIN orders o
           ON o.customer_id = c.id
          AND o.status <> 'canceled'
),
paid AS (
    SELECT customer_id,
           COUNT(*) AS paid_count
    FROM orders
    WHERE status = 'paid'
    GROUP BY customer_id
)
SELECT j.name AS customer,
       IFNULL(SUM(j.total_cents), 0) AS revenue_cents,
       COUNT(j.order_id) AS order_count,
       IFNULL(p.paid_count, 0) AS paid_count
FROM joined j
LEFT JOIN paid p ON p.customer_id = j.id
GROUP BY j.id, j.name
ORDER BY revenue_cents DESC, j.name ASC;
```

改写保留了三个关键点：`<> 'canceled'` 仍写在 ON 条件里（不是 WHERE，否则会丢掉 Dave 的空行）；`COUNT(j.order_id)` 继续只数非 NULL；GROUP BY 与 ORDER BY 的列和兜底顺序不变。

## 6. 第三步：等价验证程序（基线 + 差分）

<!-- verify:file=verify.py -->
```python
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 在 seed.sql 上实际执行 legacy.sql 得到的 golden：不要手算，必须跑出来。
GOLDEN = [
    ("Eve", 8500, 2, 1),
    ("Alice", 7500, 2, 2),
    ("Bob", 3000, 1, 1),
    ("Carol", 1200, 2, 1),
    ("Dave", 0, 0, 0),
]


def read(name):
    return (HERE / name).read_text(encoding="utf-8")


def build_database():
    connection = sqlite3.connect(":memory:")
    connection.executescript(read("schema.sql"))
    connection.executescript(read("seed.sql"))
    return connection


def rows(connection, sql):
    return [tuple(row) for row in connection.execute(sql).fetchall()]


def main():
    legacy_sql = read("legacy.sql")
    refactored_sql = read("refactored.sql")

    connection = build_database()
    legacy = rows(connection, legacy_sql)
    refactored = rows(connection, refactored_sql)
    connection.close()

    failures = 0
    if legacy != GOLDEN:
        failures += 1
        print("baseline mismatch:")
        print(f"  got      {legacy}")
        print(f"  expected {GOLDEN}")
    if refactored != legacy:
        failures += 1
        print("equivalence mismatch:")
        print(f"  legacy     {legacy}")
        print(f"  refactored {refactored}")

    if failures:
        print(f"FAILED: {failures} check(s)")
        return 1
    print(f"PASS: {len(GOLDEN)} golden rows locked; refactored result set is identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 7. 可执行验证

CI 用 `python3 .github/scripts/verify_examples.py --require-all` 把 `schema.sql`、`seed.sql`、`legacy.sql`、`refactored.sql`、`verify.py` 写入临时目录并执行 `python verify.py`；SQLite 存在于 Python 标准库，所以这条验证链零依赖、跨平台。本地可 `--only sql-legacy-report-equivalence` 单独跑。

## 8. 这个流程为什么可靠

- **SQL 的验收单位是结果集**：把「结果不变」写成 golden + 差分对比，而不是「看起来一样」。
- **隐式语义被固定**：NULL 比较、COUNT 语义、GROUP BY 选取、排序兜底，由 golden 行逐一锁死。
- **差分验证兜底**：即使 golden 有遗漏，遗留查询与重构查询也会在固定数据集上逐行比较。
- **性能目标与正确性分离**：执行计划 / 索引优化属于性能变更，应在结果集等价通过后单独评估。
