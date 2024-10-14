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
import datetime
from datetime import date

#######################################################################################

# What is the date? Normally want to run at beginning of month to bill month before
DATE      = date.today()
stop      = datetime.date(DATE.year, DATE.month, 1)
start     = stop - pd.DateOffset(months=1)


# Authenticate for API, open sheet, and get worksheet data
gc        = gspread.service_account(filename=cred_file)
sh        = gc.open("Fly Kitchen Ordering (Responses)")
wsh       = sh.get_worksheet(0)
now       = worksheet.get_all_values()

# Reformat as Pandas df, third column is delivery date, change to datetime format
df          = pd.DataFrame(now[1:], columns=now[0])
df.iloc[,3] = pd.to_datetime( df.iloc[,3] ) 


#print(sh.sheet1.get('A5'))
