## 2024-10-16 JCF
#######################################################################################

# Purpose:
# Fly kitchen billing is done in a google sheet- want to automatically process billing.

# Sources:
# Google doc API explanation:
# https://docs.gspread.org/en/latest/oauth2.html#service-account

#######################################################################################

# Path to credential .json file, needed to authorize sheet access
cred_file = '/home/jamie/fly-kitchen-billing-e82a4be570b3.json'
# Google sheet name
order_sheet_name = "Fly Kitchen Ordering (Responses)"
# Name of worksheet with billing form data
form_response_sheet = "Form Responses 1"
# Name of worksheet to write billed orders to for archive
archive_sheet = "FY26_archive"
# Name of worksheet to write billed orders to for archive
itemized_sheet = "FY26_monthly_itemized" 


#######################################################################################

import gspread
import pandas as pd
#import datetime
from datetime import date
from datetime import datetime
from itertools import compress
import generate_invoices

#######################################################################################

def load_and_prepare_orders(

    cred_file=cred_file,
    order_sheet_name=order_sheet_name,
    form_response_sheet=form_response_sheet,
    start=None,
    stop=None,
    billing_date=None,
):
    """Load Google Sheet data and return the formatted dataframe window for billing."""
    if start is None or stop is None:
        if billing_date is None:
            billing_date = date.today()
        stop = pd.Timestamp(billing_date.year, billing_date.month, 1)
        start = stop - pd.DateOffset(months=1)
    else:
        start = pd.Timestamp(start)
        stop = pd.Timestamp(stop)

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

    now = df[(df['Date'] >= start) & (df['Date'] <= stop)]

    return {
        'start': start,
        'stop': stop,
        'gc': gc,
        'sh': sh,
        'wsh': wsh,
        'all_val': all_val,
        'df': df,
        'now': now,
    }

#######################################################################################

def get_rate_df():
    """Return the rate dataframe with pricing for different container/material/special 
    combinations."""
    rate = 25
    plastic_vial = 0.8
    empty_vial = 0.5
    half_food = 0.96

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
    return(rate_df)

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

def update_billing_sheets(sh, charge_df, start, stop, all_val):
    """Update Google Sheets with billing data: itemized charges, summary bills, and archive."""
    outsheet = sh.worksheet(itemized_sheet)
    outsheet.append_rows(charge_df.values.tolist(), table_range='A1:G1')

    # For archive, still use start.month as before
    # For archive, archive all months in the period
    archive_data = []
    for month in pd.date_range(start, stop, freq='MS'):
        archive_data.extend(get_archive(all_val[1:], month.month))
    if archive_data:
        outsheet = sh.worksheet(archive_sheet)
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
    sheet_data = load_and_prepare_orders(start=start, stop=stop, billing_date=billing_date)
    start = sheet_data['start']
    stop = sheet_data['stop']

    gc = sheet_data['gc']
    sh = sheet_data['sh']
    wsh = sheet_data['wsh']
    all_val = sheet_data['all_val']
    df = sheet_data['df']
    now = sheet_data['now']

    rate_df = get_rate_df()
    charge_df = generate_charge_df(now, rate_df, start, stop)

    if update_sheets:
        simple = update_billing_sheets(sh, charge_df, start, stop, all_val)
    else:
        # Generate simple summary without updating sheets
        simple = pd.pivot_table(charge_df, values='Charges', index=['Lab'], aggfunc='sum').reset_index()
        period_str = f"{start.year}-{start.month} to {stop.year}-{stop.month}"
        simple.insert(0, 'Billing_period', period_str)

    if write_invoices:
        generate_invoices.generate_invoices(charge_df, output_dir=output_folder)

    return {
        'charge_df': charge_df,
        'simple': simple,
    }



#######################################################################################
if __name__ == '__main__':
    run_billing(write_invoices=True)



