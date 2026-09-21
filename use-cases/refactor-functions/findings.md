# Function Decomposition Challenge - Findings

## Code Selection

- **Selected scenario:** Report Generation Function with Multiple Data Transformations (Python) - `python/sales_report.py` (`generate_sales_report`, 162-line monolithic function + 4 stub helpers).
- **What it does:** Builds a sales report payload from a list of transactions, supporting date-range and custom filtering, grouping, three report types (summary/detailed/forecast), optional charts, and four output formats.
- **Verification baseline:** `python -m unittest test_sales_report` - **all 8 tests pass** before refactoring.

---

## Step 1: Identify the distinct responsibilities

The single function was doing seven jobs, interleaved with shared local state (`sales_data` mutated by reference assignment, `grouped_data`, `total_sales` recomputed mid-function):

| # | Responsibility | Lines (original) | Evidence |
| --- | --- | --- | --- |
| 1 | Input validation | 23-30 | Three `raise ValueError` guards for `sales_data`, `report_type`, `output_format` |
| 2 | Date-range filtering | 33-50 | Validates the range, parses dates, keeps in-window rows |
| 3 | Custom filter application | 53-58 | Applies arbitrary `key=value` or `key in list` filters |
| 4 | Empty-data handling | 61-68 | `print("Warning: ...")` + early empty result |
| 5 | Metrics calculation | 71-74 | `total_sales`, `avg_sale`, `max_sale`, `min_sale` |
| 6 | Grouping | 77-94 | Buckets data by a field; per-group count/total/items/average |
| 7 | Report assembly | 97-150 | Base metadata + summary section + grouping + detailed transactions |
| 8 | Forecast computation | 152-209 | Monthly aggregation, growth rates, 3-month projection |
| 9 | Chart generation | 212-240 | Sales-over-time series + grouping pie chart |
| 10 | Output dispatch | 243-250 | Returns payload or delegates to format helpers |

Ten distinct jobs in one function - the classic "god function" profile.

## Step 2: Decomposition plan

Rules applied when planning the split:

1. **One helper per responsibility** from the table above (10 tasks -> 12 helpers; a few combine related data-shaping steps).
2. **Public API unchanged** - same signature, same return shapes, same exception types/messages, same `print` warning.
3. **Pure functions where possible** - each helper takes all inputs and returns results; shared state (`sales_data`, groupings, metrics) flows through return values instead of mutation.
4. **Clear, intentional names** - each helper name states exactly what it does.

Planned helper set:

- `_validate_inputs` - argument validation (responsibility 1)
- `_filter_by_date_range` - date-range logic (2)
- `_apply_filters` - custom filters (3)
- `_empty_report_result` - empty result (4)
- `_calculate_metrics` - statistics (5)
- `_group_sales` - grouping buckets (6)
- `_build_report_header` - base metadata (7a)
- `_build_summary` - summary section (7b)
- `_build_grouping_section` - grouping section (7c)
- `_build_transactions` - detailed transactions (7d)
- `_build_forecast` - forecast section (8)
- `_build_charts` - chart payload (9)
- `_dispatch_output` - format dispatch (10)

## Step 3: Extracted helpers with clear purposes

```python
def _validate_inputs(sales_data, report_type, output_format):  # validation
def _filter_by_date_range(sales_data, date_range):             # narrows to window
def _apply_filters(sales_data, filters):                       # key/value filtering
def _empty_report_result(report_type, output_format):          # empty-result branch
def _calculate_metrics(sales_data):                            # totals, avg, max, min
def _group_sales(sales_data, grouping):                        # buckets + group stats
def _build_report_header(report_type, date_range, filters):    # metadata dict
def _build_summary(metrics):                                   # summary section dict
def _build_grouping_section(grouping, grouped_data, total):    # grouping section dict
def _build_transactions(sales_data):                           # detailed rows + calc fields
def _build_forecast(sales_data):                               # monthly/trend/projection
def _build_charts(sales_data, grouping, grouped_data):         # time + pie charts
def _dispatch_output(report_data, output_format, charts):      # format routers
```

Each helper carries a one-line docstring describing its single job. Helpers are private (underscore prefix), matching the existing stubs (`_generate_*`), so the module's public surface is unchanged: only `generate_sales_report` is importable.

## Step 4: Refactored main function

The 162-line monolith became a ~40-line orchestrator with a straight-line reading order:

```python
def generate_sales_report(sales_data, report_type='summary', date_range=None,
                         filters=None, grouping=None, include_charts=False,
                         output_format='pdf'):
    _validate_inputs(sales_data, report_type, output_format)

    sales_data = _filter_by_date_range(sales_data, date_range)
    sales_data = _apply_filters(sales_data, filters)

    if not sales_data:
        return _empty_report_result(report_type, output_format)

    metrics = _calculate_metrics(sales_data)
    grouped_data = _group_sales(sales_data, grouping) if grouping else None

    report_data = _build_report_header(report_type, date_range, filters)
    report_data['summary'] = _build_summary(metrics)

    if grouped_data is not None:
        report_data['grouping'] = _build_grouping_section(grouping, grouped_data, metrics['total_sales'])
    if report_type == 'detailed':
        report_data['transactions'] = _build_transactions(sales_data)
    if report_type == 'forecast':
        report_data['forecast'] = _build_forecast(sales_data)
    if include_charts:
        report_data['charts'] = _build_charts(sales_data, grouping, grouped_data)

    return _dispatch_output(report_data, output_format, include_charts)
```

The reading order now *is* the report-generation pipeline: validate -> filter -> early-out -> compute -> assemble sections -> render. The stub `_generate_*` format helpers are left untouched at the bottom.

## Step 5: Verify behavior is preserved

1. **Existing unit tests:** `python -m unittest test_sales_report -v` - all 8 pass on the refactored code.
2. **Differential testing** (original preserved verbatim in a side module, compared across every combination of `report_type x date_range x filters x grouping x include_charts` = 3 x 3 x 4 x 3 x 2 = **216 ordered cases**, normalized only for the `date_generated` timestamp): **all identical**.
3. **Error-path parity:** empty input, non-list input, invalid `report_type`, invalid `output_format`, missing date-range key, and start-after-end range all raise the exact same `ValueError` messages.
4. **Empty-data branch:** the `print("Warning: ...")` + JSON empty payload are byte-identical.
5. **Format dispatch:** `pdf`/`html`/`excel` delegate identically (both before and after, stubs return `None`).

Result: refactoring is behavior-preserving, not just "tests pass".

## Step 6: Benefits gained

- **Readability:** the pipeline is now visible in ~10 lines; each section's logic lives next to its name.
- **Maintainability:** a change to forecasting touches only `_build_forecast`; a new report type is a new section helper + one `if` in the orchestrator.
- **Testability:** each helper is independently testable (e.g., `_build_forecast` can be unit-tested without the filtering stage).
- **Reuse:** `_calculate_metrics` and `_build_charts` are general enough to serve other features (dashboards, exports) directly.
- **Reduced cognitive load:** no more tracing mutated `sales_data`/`grouped_data` through 162 lines - every transformation now has a visible input->output contract.

---

## Reflection Questions

**1. How did breaking down the function improve its readability and maintainability?**

Readability improved the most. Before, understanding the function meant holding a 162-line mental model with variable reuse (e.g., `sales_data` reassigned twice, `total_sales` used by both summary and grouping). After, the top-level function reads like a checklist, and any single behaviour can be read, reasoned about, and tested in isolation. Maintainability follows: adding a new output format is one branch in `_dispatch_output`; changing date-range semantics is one helper. The line count grew slightly (~13 helpers vs. 1 monolith), but lines that *do* something identifiable outnumber glue and commentary.

**2. What was the most challenging part of decomposing the function?**

**Preserving invisible behaviour exactly.** The riskiest parts were the subtle coupling points: (a) the forecast section's growth-rate list only appends when `prev_amount > 0`, so the `growth_rates` dict assumed alignment with `sorted_months` - a latent quirk that must be reproduced bit-for-bit; (b) dict insertion order, because JSON consumers may rely on it; (c) the `print` warning side effect; (d) the `date_generated` timestamp set at report-build time. The differential harness was essential - it proved equivalence across 216 combinations and the exact `ValueError` strings that the unit tests alone would never cover.

**3. Which extracted function would be most reusable in other contexts?**

**`_calculate_metrics`** - computing `total`, `average`, `max`, `min` over a list is a generic analytics operation applicable to dashboards, inventory views, export summaries, or any other aggregate display. `_build_charts` (labels/data shaping) is a close second, since it is already format-agnostic (it returns plain dicts, not Plotly/HTML objects). By contrast, `_build_forecast` and `_group_sales` are more bound to this module's data model and report structure.