# 实战样例：遗留 Java 代码的行为基线（无测试框架）

演示工作流 2：没有 JUnit / Maven 的遗留 Java 代码，先用「退出码断言程序」捕捉当前行为（含 NPE 与 double 运算顺序这类隐式规则），再做结构化重构，最后逐例差分证明等价。Java 版策略 C 全景见 [java-order-calculator-strategy-c.md](java-order-calculator-strategy-c.md)。

本样例不是纸面代码：带 `<!-- verify:file=... -->` 标记的代码块会被 [.github/scripts/verify_examples.py](../.github/scripts/verify_examples.py) 还原到临时目录，CI 用 JDK 17 实际执行 `javac` + `java Verify`；跑不过就红。

<!-- verify:run
javac Item.java Order.java LegacyOrderCalculator.java RefactoredOrderCalculator.java Verify.java
java Verify
-->

## 1. 遗留代码（嵌套 5 层、魔数散落）

<!-- verify:file=Item.java -->
```java
public class Item {
    public final double price;
    public final int quantity;
    public final String category;

    public Item(double price, int quantity, String category) {
        this.price = price;
        this.quantity = quantity;
        this.category = category;
    }
}
```

<!-- verify:file=Order.java -->
```java
public class Order {
    public final Item[] items;
    public final String country;

    public Order(Item[] items, String country) {
        this.items = items;
        this.country = country;
    }
}
```

<!-- verify:file=LegacyOrderCalculator.java -->
```java
public class LegacyOrderCalculator {
    public static double total(Order order) {
        double total = 0;
        if (order != null) {
            if (order.items != null) {
                for (Item item : order.items) {
                    if (item != null) {
                        double price = item.price;
                        if (item.quantity > 0) {
                            price = price * item.quantity;
                        } else {
                            price = 0;
                        }
                        if (item.category.equals("BOOK")) {
                            price = price * 0.9;
                        } else if (item.category.equals("ELECTRONICS")) {
                            price = price * 0.95;
                        }
                        total = total + price;
                    }
                }
            }
        }
        if (total > 100) { total = total * 0.98; }
        if (order != null && order.country != null) {
            if (order.country.equals("US")) {
                total = total * 1.08;
            } else {
                total = total * 1.2;
            }
        }
        if (total > 0) { total = total + 5; }
        return total;
    }
}
```

**为什么危险**：`category` 为 null 时 `.equals` 直接 NPE；满减阈值是严格 `> 100`；税费在满减之后乘、运费最后加，每一步 double 运算顺序都会影响末位；数量 ≤ 0 被静默按 0 计；魔数与嵌套 if 让「改一处、动全身」。

## 2. 用策略 C 生成的提示词（核心片段）

```text
你是资深 Java 专家，专注在不改变行为的前提下做重构。

【硬约束】
1. 外部行为 100% 一致：不改公开 API、返回值、异常类型；
2. category 为 null 时必须继续抛 NullPointerException，不得顺手「修 bug」；
3. double 的计算顺序（分类折扣 → 求和 → 满减 → 税 → 运费）必须保持；
4. 不新增第三方依赖，不引入 BigDecimal 改变数值语义。

【重构目标】
1. 提取子方法，嵌套 5 层 → 1 层；
2. 用具名常量替换 0.9 / 0.95 / 0.98 / 100 / 1.08 / 1.2 / 5；
3. 分类折扣、满减、税费、运费各司其职。

【验收标准】
- 测试命令：javac Item.java Order.java LegacyOrderCalculator.java RefactoredOrderCalculator.java Verify.java && java Verify
- 用例：空订单 → 0；BOOK 100×1 → 102.2；ELECTRONICS 200×2 → 451.88；category=null → 与原实现一样抛 NPE。
```

## 3. 行为基线 + 差分验证（无测试框架，用退出码断言）

没有 JUnit 时，用一个 `main` 程序把「旧实现 vs 新实现」逐例比较：任一用例不一致或 NPE 行为不同就以非零码退出。

<!-- verify:file=RefactoredOrderCalculator.java -->
```java
public class RefactoredOrderCalculator {
    private static final double BOOK_DISCOUNT = 0.9;
    private static final double ELECTRONICS_DISCOUNT = 0.95;
    private static final double ORDER_DISCOUNT = 0.98;
    private static final double ORDER_DISCOUNT_THRESHOLD = 100;
    private static final double US_TAX = 1.08;
    private static final double OTHER_TAX = 1.2;
    private static final double SHIPPING = 5;

    public static double total(Order order) {
        double subtotal = subtotal(order);
        subtotal = applyOrderDiscount(subtotal);
        subtotal = applyTax(subtotal, order);
        return applyShipping(subtotal);
    }

    private static double subtotal(Order order) {
        if (order == null || order.items == null) return 0;
        double total = 0;
        for (Item item : order.items) {
            if (item == null) continue;
            double price = item.quantity > 0 ? item.price * item.quantity : 0;
            total = total + applyCategoryDiscount(price, item.category);
        }
        return total;
    }

    private static double applyCategoryDiscount(double price, String category) {
        if (category.equals("BOOK")) return price * BOOK_DISCOUNT;
        if (category.equals("ELECTRONICS")) return price * ELECTRONICS_DISCOUNT;
        return price;
    }

    private static double applyOrderDiscount(double total) {
        return total > ORDER_DISCOUNT_THRESHOLD ? total * ORDER_DISCOUNT : total;
    }

    private static double applyTax(double total, Order order) {
        if (order != null && order.country != null) {
            if (order.country.equals("US")) return total * US_TAX;
            return total * OTHER_TAX;
        }
        return total;
    }

    private static double applyShipping(double total) {
        return total > 0 ? total + SHIPPING : total;
    }
}
```

<!-- verify:file=Verify.java -->
```java
public class Verify {
    private interface Calculator {
        double total(Order order);
    }

    public static void main(String[] args) {
        Calculator legacy = LegacyOrderCalculator::total;
        Calculator refactored = RefactoredOrderCalculator::total;

        Order[] orders = {
            new Order(null, null),
            new Order(new Item[0], "US"),
            new Order(new Item[]{null}, "EU"),
            new Order(new Item[]{new Item(100, 1, "BOOK")}, "US"),
            new Order(new Item[]{new Item(200, 2, "ELECTRONICS")}, "EU"),
            new Order(new Item[]{new Item(100, 1, "OTHER")}, null),
            new Order(new Item[]{new Item(100, 3, "BOOK"), new Item(50, 0, "OTHER")}, "US"),
            new Order(new Item[]{new Item(33.33, 7, "BOOK"), new Item(19.99, 2, "ELECTRONICS")}, "EU"),
            new Order(new Item[]{new Item(0.1, 1, "OTHER")}, "US"),
            new Order(new Item[]{new Item(50, 1, "OTHER")}, "CA"),
            new Order(new Item[]{new Item(34, 3, "OTHER")}, "US"),
        };
        for (int i = 0; i < orders.length; i++) {
            double before = legacy.total(orders[i]);
            double after = refactored.total(orders[i]);
            if (Double.compare(before, after) != 0) {
                System.out.println("case " + i + " mismatch: legacy=" + before + " refactored=" + after);
                System.exit(1);
            }
        }

        Order nullCategory = new Order(new Item[]{new Item(10, 1, null)}, "US");
        boolean legacyThrew = throwsNullPointer(legacy, nullCategory);
        boolean refactoredThrew = throwsNullPointer(refactored, nullCategory);
        if (legacyThrew != refactoredThrew) {
            System.out.println("null category mismatch: legacy=" + legacyThrew + " refactored=" + refactoredThrew);
            System.exit(1);
        }
        if (!legacyThrew) {
            System.out.println("expected NullPointerException on null category");
            System.exit(1);
        }
        System.out.println("java differential checks passed");
    }

    private static boolean throwsNullPointer(Calculator calculator, Order order) {
        try {
            calculator.total(order);
            return false;
        } catch (NullPointerException expected) {
            return true;
        }
    }
}
```

## 4. 为什么这一版可靠

- **异常行为也是行为**：`category.equals(...)` 保留了 null 时的 NPE；把它改成 `"BOOK".equals(category)` 属于行为变更，应另开变更单。
- **double 运算顺序不变**：分类折扣 → 求和 → 满减 → 税 → 运费，与旧实现逐句对应，`Double.compare` 直接比较结果位。
- **边界被锁死**：满减阈值严格 `> 100`、数量 ≤ 0 按 0 计、总价 ≤ 0 不加运费，全部由差分用例覆盖。
- **无框架也能验收**：`javac && java Verify` 用退出码表达「等价」，CI 直接执行，不依赖 Maven / JUnit。

## 5. 可执行验证

六个代码块分别标注了最终文件名。CI 安装 JDK 17 后执行上方 `verify:run` 命令：`javac` 编译全部源码，`java Verify` 做逐例差分与 NPE 断言；本地可只跑该样例：`python3 .github/scripts/verify_examples.py --only java-legacy-order-total`。
