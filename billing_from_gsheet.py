## 2024-10-16 JCF
#######################################################################################

# Purpose:
# Fly kitchen billing is done in a google sheet- want to automatically process billing.

# Sources:
# Google doc API explanation:
# https://docs.gspread.org/en/latest/oauth2.html#service-account

#######################################################################################

import gspread
import pandas as pd
#import datetime
from datetime import date
from datetime import datetime
from itertools import compress
import generate_invoices
import yaml
import argparse

# Load configuration from config.yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

#######################################################################################

def load_raw_orders(cred_file=None, order_sheet_name=None, form_response_sheet=None):
    """Load raw order data from Google Sheet and return dataframe and connection objects."""
    if cred_file is None:
        cred_file = config['credentials']['file_path']
    if order_sheet_name is None:
        order_sheet_name = config['sheets']['order_sheet_name']
    if form_response_sheet is None:
        form_response_sheet = config['sheets']['form_response_sheet']
    gc = gspread.service_account(filename=cred_file)
    sh = gc.open(order_sheet_name)
    wsh = sh.worksheet(form_response_sheet)
    all_val = wsh.get_all_values()

    header = ['Timestamp', 'Email', 'Lab', 'Date', 'Container', 'Material', 'Number', 'Special']
    df = pd.DataFrame(all_val[1:], columns=header)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Number'] = df['Number'].astype(float)
    df['Container'] = df.Container.str.split(' ').str[0]
    df['Special'] = df.Special.str.split(' ').str[0]

    return df, gc, sh, wsh, all_val

def filter_orders_by_period(df, start, stop):
    """Filter orders dataframe to the specified date range (inclusive)."""
    now = df[(df['Date'] >= start) & (df['Date'] <= stop)]
    return now

#######################################################################################

def get_rate_df():
    """Return the rate dataframe with pricing for different container/material/special 
    combinations."""
    rates = config['rates']
    rate = rates['base_rate']
    plastic_vial = rates['plastic_vial_multiplier']
    empty_vial = rates['empty_vial_multiplier']
    half_food = rates['half_food_multiplier']

    rate_table = [
        ['Container', 'Material', 'Special', 'Price'],
        ['Bottles', 'Plastic', '', rate],
        ['Bottles', 'Plastic', 'Unplugged', rate],
        ['Bottles', 'Glass', '', rate],
        ['Vials', 'Plastic', '', rate * plastic_vial],
        ['Vials', 'Plastic', 'Unplugged', rate * plastic_vial],
        ['Vials', 'Plastic', 'Grace', rate * plastic_vial],
        ['Vials', 'Glass', '', rate],
        ['Vials', 'Glass', 'Unplugged', rate],
        ['Vials', 'Glass', 'Half', rate * half_food],
        ['Vials', 'Glass', 'Empty', rate * empty_vial],
    ]
    rate_df = pd.DataFrame(rate_table[1:], columns=rate_table[0])
    return rate_df

def get_fiscal_quarter(month, year):
    """Return fiscal year quarter label for a given month/year.

    Fiscal year starts in July:
      - Q1: Jul-Aug-Sep
      - Q2: Oct-Nov-Dec
      - Q3: Jan-Feb-Mar
      - Q4: Apr-May-Jun

    Example:
      - July 2025 -> FY26Q1
      - Feb 2026 -> FY26Q3
    """
    if month in [7, 8, 9]:
        q = 'Q1'
        fy = year + 1
    elif month in [10, 11, 12]:
        q = 'Q2'
        fy = year + 1
    elif month in [1, 2, 3]:
        q = 'Q3'
        fy = year
    else:
        q = 'Q4'
        fy = year

    return f"FY{str(fy)[-2:]}{q}"

#######################################################################################

def generate_charge_df(now, rate_df, start, stop):
    """Generate the charge dataframe by pivoting orders, merging rates, and calculating charges.
    
    If the period spans multiple months, itemizes charges by month for each lab.
    """
    # Get unique months in the period
    now_copy = now.copy()
    now_copy['Month'] = now_copy['Date'].dt.to_period('M')
    unique_months = now_copy['Month'].unique()
    
    monthly_charges = []
    
    for month in unique_months:
        month_data = now_copy[now_copy['Month'] == month]
        if month_data.empty:
            continue
            
        pivot = pd.pivot_table(
            month_data,
            values='Number',
            index=['Lab', 'Container', 'Material', 'Special'],
            aggfunc='sum',
        ).reset_index()

        charge_df = pd.merge(
            pivot,
            rate_df,
            how='left',
            on=['Container', 'Material', 'Special'],
        )
        charge_df['Charges'] = charge_df['Number'] * charge_df['Price']
        charge_df.insert(0, 'Billing_period', str(month))
        charge_df['Quarter'] = get_fiscal_quarter(month.month, month.year)
        
        monthly_charges.append(charge_df)
    
    if not monthly_charges:
        # Fallback for empty data
        return pd.DataFrame(columns=['Billing_period', 'Lab', 'Container', 'Material', 'Special', 'Number', 'Price', 'Charges', 'Quarter'])
    
    return pd.concat(monthly_charges, ignore_index=True)

#######################################################################################

def save_charges_to_sheet(sh, charge_df):
    """Save charge dataframe to the itemized sheet."""
    outsheet = sh.worksheet(config['sheets']['itemized_sheet'])
    outsheet.append_rows(charge_df.values.tolist(), table_range='A1:G1')

def save_archive_to_sheet(sh, all_val, start, stop):
    """Save archived orders to the archive sheet for the billing period."""
    archive_data = []
    for month in pd.date_range(start, stop, freq='MS'):
        archive_data.extend(get_archive(all_val[1:], month.month))
    if archive_data:
        outsheet = sh.worksheet(config['sheets']['archive_sheet'])
        outsheet.append_rows(archive_data, table_range='A1:H1')

#######################################################################################

def get_archive(l, m):
	'''
	From a nested list (all_values), where the third entry is the order date,
	filter for entries from month m
	'''
	o = list( compress(l,
		 	[ datetime.strptime(x[3], '%m/%d/%Y').month == m for x in l ] ) )
	return o

#######################################################################################

# Helper to run the billing workflow with optional start and stop dates

def run_billing(
    start=None,
    stop=None,
    billing_date=None,
    output_folder='invoices',
    write_invoices=False,
    update_sheets=True,
):
    """Run the complete billing workflow: load data, generate charges, update sheets, generate invoices."""
    # Determine billing period
    if start is None or stop is None:
        if billing_date is None:
            billing_date = date.today()
        stop = pd.Timestamp(billing_date.year, billing_date.month, 1)
        start = stop - pd.DateOffset(months=1)
    else:
        start = pd.Timestamp(start)
        stop = pd.Timestamp(stop)

    # Load raw data from sheet
    df, gc, sh, wsh, all_val = load_raw_orders()

    # Filter orders for the billing period
    now = filter_orders_by_period(df, start, stop)

    # Generate charges
    rate_df = get_rate_df()
    charge_df = generate_charge_df(now, rate_df, start, stop)

    # Update sheets if requested
    if update_sheets:
        save_charges_to_sheet(sh, charge_df)
        save_archive_to_sheet(sh, all_val, start, stop)
        # Generate simple summary
        simple = pd.pivot_table(charge_df, values='Charges', index=['Lab'], aggfunc='sum').reset_index()
        period_str = f"{start.year}-{start.month} to {stop.year}-{stop.month}"
        simple.insert(0, 'Billing_period', period_str)
    else:
        # Generate simple summary without updating sheets
        simple = pd.pivot_table(charge_df, values='Charges', index=['Lab'], aggfunc='sum').reset_index()
        period_str = f"{start.year}-{start.month} to {stop.year}-{stop.month}"
        simple.insert(0, 'Billing_period', period_str)

    # Generate invoices if requested
    if write_invoices:
        generate_invoices.generate_invoices(charge_df, output_dir=output_folder)

    return {
        'charge_df': charge_df,
        'simple': simple,
    }



#######################################################################################
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run fly kitchen billing workflow')
    parser.add_argument('--start', type=str, help='Start date for billing period (YYYY-MM-DD)')
    parser.add_argument('--stop', type=str, help='Stop date for billing period (YYYY-MM-DD)')
    parser.add_argument('--billing-date', type=str, help='Billing date for automatic period calculation (YYYY-MM-DD)')
    parser.add_argument('--output-folder', type=str, default='invoices', help='Output folder for invoices (default: invoices)')
    parser.add_argument('--write-invoices', action='store_true', help='Generate PDF invoices')
    parser.add_argument('--no-update-sheets', action='store_true', help='Skip updating Google Sheets')
    
    args = parser.parse_args()
    
    # Convert billing_date string to date object if provided
    billing_date = None
    if args.billing_date:
        billing_date = datetime.strptime(args.billing_date, '%Y-%m-%d').date()
    
    # Run billing with parsed arguments
    result = run_billing(
        start=args.start,
        stop=args.stop,
        billing_date=billing_date,
        output_folder=args.output_folder,
        write_invoices=args.write_invoices,
        update_sheets=not args.no_update_sheets
    )
    
    print("Billing completed successfully!")
    print(f"Processed {len(result['charge_df'])} charge entries")
    print(f"Generated invoices for {len(result['simple'])} labs")



