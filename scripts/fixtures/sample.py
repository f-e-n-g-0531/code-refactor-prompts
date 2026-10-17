def total(items):
    total = 0
    for item in items:
        if item.get("qty", 0) <= 0:
            continue
        total += item["price"] * item["qty"]
    return total
