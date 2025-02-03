## 2024-10-16 JCF
#######################################################################################

# Purpose:
# Fly kitchen billing is done in a google sheet- want to automatically process billing.

# Sources:
# Google doc API explanation:
# https://docs.gspread.org/en/latest/oauth2.html#service-account
#######################################################################################

cred_file = '/home/jamie/fly-kitchen-billing-e82a4be570b3.json'

#######################################################################################

import gspread
import pandas as pd
#import datetime
from datetime import date
from datetime import datetime
from itertools import compress

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

# What is the date? Normally want to run at beginning of month to bill month before
DATE      = date.today()
stop      = pd.Timestamp(DATE.year, DATE.month, 1)
start     = stop - pd.DateOffset(months=1)

# Authenticate for API, open sheet, and get worksheet data
gc        = gspread.service_account(filename=cred_file)
sh        = gc.open("Fly Kitchen Ordering (Responses)")
wsh       = sh.get_worksheet(0)
all_val   = wsh.get_all_values()

# Reformat as Pandas df, third column is delivery date, change to datetime format,
#	
header          = ['Timestamp', 'Email', 'Lab', 'Date', 'Container', 'Material', 'Number', 'Special']
df              = pd.DataFrame(all_val[1:], columns=header)
df['Date']      = pd.to_datetime( df['Date'] )
df['Number']    = df['Number'].astype(float)
df['Container'] = df.Container.str.split(' ').str[0]
df['Special']   = df.Special.str.split(' ').str[0]

now        = df[(df['Date'] > start) & (df['Date'] < stop)]

#######################################################################################
# Rate and proportional rates for plastic/empty
rate         = 25
plastic_vial = 0.8
empty_vial   = 0.5
half_food    = 0.96

rate_table = [ ['Container', 'Material','Special', 'Price'], 
['Bottles', 'Plastic', '', rate], 
['Bottles', 'Glass', '', rate],
['Vials', 'Plastic', '', rate*plastic_vial], 
['Vials', 'Plastic', 'Unplugged', rate*plastic_vial], 
['Vials', 'Glass', '',rate],
['Vials', 'Glass', 'Half',rate*half_food],
['Vials', 'Glass', 'Empty', rate*empty_vial] ]

rate_df = pd.DataFrame(rate_table[1:], columns=rate_table[0])

#######################################################################################
# Pivot the totals
pivot = pd.pivot_table(now, values='Number', index=['Lab', 'Container', 'Material','Special'], aggfunc="sum").reset_index()

# Merge the monthly totals with rates per item and multiple by unit cost to get charges
charge_df            = pd.merge(pivot, rate_df, how='left',on=['Container', 'Material', 'Special']) 
charge_df['Charges'] = charge_df['Number'] * charge_df['Price']
charge_df.insert(0, 'Billing_period', str(start.year) + '-' + str(start.month))


#######################################################################################
# Write output
outsheet = sh.worksheet("FY25_monthly_itemized")
outsheet.append_rows( charge_df.values.tolist(), table_range="A1:G1")

simple = pd.pivot_table(charge_df, values='Charges', index=['Lab'], aggfunc="sum").reset_index()
simple.insert(0, 'Billing_period', str(start.year) + '-' + str(start.month))

outsheet = sh.worksheet("FY25_monthly_bill")
outsheet.append_rows( simple.values.tolist(), table_range="A1:C1")

# Write billed entries to archive
outsheet = sh.worksheet("FY25-archive")
outsheet.append_rows( get_archive( all_val[1:], start.month), table_range="A1:H1")

# next remove billed rows









#print(sh.sheet1.get('A5'))
