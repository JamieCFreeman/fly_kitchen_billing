# fly_kitchen_billing

Automate reading of Google sheet with fly kitchen orders to generate monthly user charges and PDF invoices.

## Setup

1. Install Python dependencies:

```bash
pip install pandas gspread reportlab
```

2. Ensure `cred_file` in `billing_from_gsheet.py` points to your service account JSON credential file.

## Main workflow

The core script is `billing_from_gsheet.py`.

### Basic run (single period via start/stop)

```python
from billing_from_gsheet import run_billing

result = run_billing(
    start='2025-12-01',
    stop='2026-03-31',
    write_invoices=True,
    update_sheets=True
)

print(result['simple'])  # summary charges per Lab
```

### Run without writing Google sheets (dry-run)

```python
result = run_billing(
    start='2025-12-01',
    stop='2026-03-31',
    write_invoices=True,
    update_sheets=False
)
```

## Date behavior

- `start` / `stop` are inclusive (billing range is `>= start` and `<= stop`).
- If not provided, `billing_date` sets `stop` to first of that month and `start` to the first of prior month.

## Invoice generation

- The helper script is `generate_invoices.py`.
- Use a CSV from `charge_df`:

```python
charge_df.to_csv('charges.csv', index=False)
python generate_invoices.py --input charges.csv --output invoices
```

- This writes invoices under `invoices/<period>/invoice_<lab>_<period>_<ts>.pdf`.

## Notes

- Ensure Google sheet tabs exist:
  - `FY26_monthly_itemized`
  - `FY26_monthly_bill`
  - `FY26_archive`

- For ongoing fiscal year billing, the quarter value is in `charge_df['Quarter']` and follows the July-based fiscal schedule (FY starts July).
