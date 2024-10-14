## 2024-10-16 JCF

# Purpose:
# Fly kitchen billing is done in a google sheet- want to automatically process billing.

# Sources:
# Google doc API explanation:
# https://docs.gspread.org/en/latest/oauth2.html#service-account

cred_file = '/home/jamie/fly-kitchen-billing-e82a4be570b3.json'

import gspread


gc = gspread.service_account(filename=cred_file)

sh = gc.open("Fly Kitchen Ordering (Responses)")

print(sh.sheet1.get('Form Responses 1'))
