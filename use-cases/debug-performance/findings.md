# Performance Optimization Challenge - Findings

## Code Selection

- **Selected scenario:** Slow Code Analysis - Python data processing function (`python/inventory_analysis.py`)
- **Scenario context (from the exercise notes):** `find_product_combinations` finds all product pairs whose combined price falls within `target_price ± price_margin`. It is called on every visit to the "Product Recommendations" page, typically with 5,000+ products, in a Python 3.9 web environment with 4GB RAM.
- **Prompt used:** "Identifying Performance Bottlenecks - Prompt 1: Slow Code Analysis", including the "measure before and after" practice from the Common Pitfalls (never optimize without measurement).

---

## Step 1: AI's Slow Code Analysis (the prompt response, applied to this code)

**1. Why this code might be slow (in simple terms):**

The function compares every product with *every* product, twice. It iterates each ordered pair `(i, j)` where `i != j`, which is `n × (n-1)` comparisons (25 million for 5,000 products - for *each* of the two orderings of every pair). Worse, every time it finds a valid combination it re-scans the entire `results` list to check for a duplicate, so the cost grows quadratically with the number of results too.

**2. Specific operations causing the slowdown:**

- **The `any(...)` duplicate scan (the dominant cost):** for every in-range pair, `if not any(r['product1']['id'] == ... for r in results)` walks the whole growing `results` list. Results grow ~O(n²), and this scan is done ~O(n²) times, so the loop is effectively O(n² × results) ≈ **O(n⁴)** in the worst case. This is what makes it catastrophic at scale.
- **Doubling the work:** `for j in range(len(products))` with `if i != j` examines both `(a, b)` and `(b, a)` for every pair, then throws one away. All the `i == j` iterations are wasted.
- **Repeated dict lookups:** `product1['price']` and `product2['price']` are re-read from the dicts on every single iteration.
- **The price-range check recomputed each time:** `(target_price - price_margin) <= combined_price <= ...` re-subtracts the constants in the innermost loop.

**3. Suggested improvements (2-3):**

1. Iterate each unordered pair once: `for j in range(i + 1, n)`. This halves the comparisons *and removes the entire `any()` scan* (a duplicate can never appear if we never look at the second ordering).
2. Hoist the price list and the boundary values out of the loop; index a plain `prices` list instead of dict-lookup per iteration, and precompute `low`/`high` and each outer product's partner range once.
3. (Optional, noted but not applied) Sorting prices and binary-searching the partner range would reduce *comparisons* to O(n log n), but the output itself is O(number of pairs), so for this task's result volumes the win is marginal and the code gets harder to read - not justified.

**4. Performance concepts to learn:** algorithmic complexity (why O(n²) nested loops + an O(results) scan inside becomes effectively O(n⁴)); the difference between *comparisons* and *result generation* (you cannot generate fewer than the number of answers); hoisting loop invariants; and "measure first" - the 80/20 rule, where the `any()` scan was 20% of the code causing ~99% of the runtime.

**5. Measurement tools/techniques:** `time.perf_counter` around the call (used), stdout redirection so progress prints don't pollute timing, `cProfile` to confirm the `any()` line dominates, and back-of-the-envelope extrapolation for sizes too big to run directly.

---

## Step 2: Baseline measurement (before)

Measured with a deterministic dataset (`random.seed(42)`, prices uniform in `[5, 500]`, `target_price=500`, `margin=50`), stdout suppressed:

| Products (n) | Combinations | Baseline time |
| --- | --- | --- |
| 100 | 979 | 0.23 s |
| 200 | 3,957 | 2.45 s |
| 300 | 8,806 | 17.15 s |
| 450 | 19,558 | 66.93 s |
| 500 | ~24,000 | **> 120 s** (stopped) |
| 5,000 | ~2.4M | extrapolated ~**days** (not runnable) |

The timing curve (`0.23 → 2.45 → 17.15 → 66.93` as n goes `100 → 200 → 300 → 450`) is steeper than quadratic - consistent with the O(n⁴)-style `any()` scan, not the naive O(n²) the loop structure suggests. Note: the exercise notes quote "20-30 seconds for 5,000 products", but actual behaviour for this code is dramatically worse - the notes' figure is unattainable for these inputs, which is itself a learning point (never trust reported timings; measure).

---

## Step 3: Optimized implementation

Applied to `python/inventory_analysis.py`, preserving the exact result (verified below):

```python
# Work with plain prices instead of repeated dict lookups on every iteration
prices = [product['price'] for product in products]
low = target_price - price_margin
high = target_price + price_margin
n = len(products)

# Each unordered pair is visited exactly once (j starts at i+1), which
# removes the O(len(results)) duplicate scan and halves the work.
for i in range(n - 1):
    if i % 100 == 0:
        print(f"Processing product {i+1} of {n}")
    product1 = products[i]
    price1 = prices[i]
    min_partner = low - price1
    max_partner = high - price1
    for j in range(i + 1, n):
        price2 = prices[j]
        # Equivalent to (target_price - margin) <= price1 + price2 <= (target_price + margin)
        if min_partner <= price2 <= max_partner:
            combined_price = price1 + price2
            results.append({...})
```

Changes made:
1. `for j in range(i + 1, n)` - each unordered pair handled once; duplicate scan (`any(...)`) deleted.
2. `prices` list built once, outer `price1` and partner range (`low - price1`, `high - price1`) hoisted out of the inner loop.
3. Constant `low`/`high` computed once instead of inside the inner loop.
4. Iteration count drops from `n×(n-1)` to `n×(n-1)/2`.

The `product1`/`product2` assignment, combination ordering, deduplication and final sort are all unchanged, so the output is byte-for-byte identical (including tie ordering, because the original also kept the lower-index product as `product1`).

**Correctness verification:** compared against the original function with identical seeded data at several sizes using deep equality (`expected == actual`):

| Size | Exact match |
| --- | --- |
| 10 | True |
| 50 | True |
| 100 | True |
| 300 | True |

(The comparison at larger sizes is impractical because the original needs hours at n=2000 and days at n=5000.)

---

## Step 4: Post-optimization measurement (after)

Same dataset/seed, same harness:

| Products (n) | Combinations | Optimized time | Baseline time | Speedup |
| --- | --- | --- | --- | --- |
| 100 | 979 | 0.008 s | 0.23 s | ~30× |
| 200 | 3,957 | 0.017 s | 2.45 s | ~145× |
| 300 | 8,806 | 0.028 s | 17.15 s | ~610× |
| 450 | 19,558 | 0.055 s | 66.93 s | ~1,200× |
| 2,000 | 387,605 | 0.70 s | hours (not run) | >1,000× |
| 5,000 | 2,432,833 | **6.37 s** | days (not run) | enormous |

End-to-end script (`python inventory_analysis.py`) with 5,000 products now completes in **~5.3 seconds** including progress output and data generation (the exercise's "Product Recommendations" page target metric).

The optimizations were decisive and justified: at the real workload (5,000 products) the function went from effectively unbounded (would take days, causing timeouts/crashes) to ~6 seconds - usable in a request handler. All three changes were algorithmic/structure-level, not micro-optimizations that sacrifice readability.

---

## Step 5: Key learnings & reflection

**How did the optimization change your understanding of the algorithm and memory management?**

It changed the picture from "an O(n²) loop that is presumably slow but tolerable" to "an effectively O(n⁴)-cost function dominated by an ugly duplicate check." The biggest realisation: **complexity is determined by the worst line, not the loop you intended.** The `any(...)` scan turned an O(n²) algorithm into something far worse, and no amount of micro-tweaking constant factors would ever have fixed it. Memory-wise, the results list (up to ~2.4M dicts) is the authentic output and cannot be avoided; the fix kept memory to that essential footprint.

**What performance improvements did you achieve? Were they significant enough?**

Yes, by an overwhelming margin: ~610× at n=300, ~1,200× at n=450, and from *days to ~6 seconds* at n=5,000 - turning a function that crashes a request into one that completes well within a typical page-load budget. The larger the data, the bigger the win, because the fix removed a super-linear term. Fully justified; the code is also *simpler* (one loop level removed, no generator scan).

**What did you learn about performance bottlenecks that you didn't know before?**

1. A "small" nested loop can hide O(n² · k) hidden work when an inner list-scan (like the duplicate check) is present - the stated O(n²) is misleading.
2. Reported timings ("20-30 seconds") should never be trusted; the measured curve showed the real code is far slower than claimed. Always produce your own numbers.
3. **Measure, then optimize:** the `any()` scan was 20% of the lines but ~99% of the runtime, exactly the 80/20 rule - had I "optimized" the inner loop body for speed first, I'd have gained nothing.
4. Removing redundancy (visiting each pair once) is free money: it halves work *and* deletes an entire class of code (the dedup scan).

**How would you approach similar performance issues in the future?**

Follow the same discipline: (1) profile/measure first with a representative dataset, (2) identify the worst-order operation, not the most-visible loop, (3) prefer structural/algorithmic changes (fewer iterations, less work per iteration, hoisted invariants) before micro-optimizations, (4) verify the optimized output equals the original on the actual data, (5) re-measure on the same harness for an honest before/after.

**What tools or techniques would you use to identify similar issues proactively?**

- `cProfile` / `python -m cProfile` to confirm which line dominates (this would immediately point at the `any(...)` line).
- `time.perf_counter` micro-benchmarks with a fixed seed for reproducible before/after numbers (used here).
- Scaling runs (n = 100/200/300/450) to reveal the complexity curve instead of a single timing at one size.
- `tracemalloc`/`memory_profiler` if memory were the constraint (it wasn't the limiting factor here).
- Pre-commit linting/ANALYSIS rules that flag `any(... for r in results)`-style linear scans inside nested loops, or a CI performance regression test that fails if the 5,000-product case drifts above a time budget.