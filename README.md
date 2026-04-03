# fly_kitchen_billing

Automate reading of Google sheet with fly kitchen orders to generate monthly user charges and PDF invoices.

## Setup

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Configure your settings in `config.yaml`:
   - Update `credentials.file_path` to point to your Google service account JSON file
   - Update sheet names if different from defaults
   - Modify base rates and multipliers if pricing changes

## Configuration

The system uses `config.yaml` for all configuration:

- **credentials**: Google service account JSON file path
- **sheets**: Google Sheets names and worksheet names
- **rates**: Base pricing rate and multipliers (the detailed rate table is generated automatically)

## Command Line Usage

Run the billing script directly from the command line:

```bash
# Basic usage with date range
python billing_from_gsheet.py --start 2025-12-01 --stop 2026-03-31 --write-invoices

# Dry run (no sheet updates)
python billing_from_gsheet.py --start 2025-12-01 --stop 2026-03-31 --write-invoices --no-update-sheets

# Use billing date for automatic period calculation (last month)
python billing_from_gsheet.py --billing-date 2026-04-01 --write-invoices

# Custom output folder
python billing_from_gsheet.py --start 2025-12-01 --stop 2026-03-31 --output-folder custom_invoices --write-invoices
```

### Command Line Options

- `--start`: Start date for billing period (YYYY-MM-DD)
- `--stop`: Stop date for billing period (YYYY-MM-DD)  
- `--billing-date`: Billing date for automatic period calculation (uses previous month)
- `--output-folder`: Output folder for invoices (default: invoices)
- `--write-invoices`: Generate PDF invoices
- `--no-update-sheets`: Skip updating Google Sheets (dry run mode)

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
