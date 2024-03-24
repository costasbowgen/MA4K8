import ccxt
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm
binance = ccxt.binance()
#Read in actual option prices

file_path_ind = ["datasets/2023/deribit_options_chain_2023-01-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-02-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-03-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-04-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-05-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-06-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-07-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-08-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-09-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-10-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-11-01_OPTIONS.csv.gz",
                 "datasets/2023/deribit_options_chain_2023-12-01_OPTIONS.csv.gz"]

month_ind = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
month_num = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]

i = 0
while i < 12:
    file_path = file_path_ind[i]
    month = month_ind[i]
    monthN = month_num[i]
    new_df = pd.read_csv(file_path, compression= "gzip")
    btc_df = new_df[new_df['symbol'].str.contains('BTC')]
    print("Length of bitcoin: ", len(btc_df))
    monthBtc_df = btc_df[btc_df["symbol"].str.contains(month)]
    print("Length of month expire: ", len(monthBtc_df))
    delta_df = monthBtc_df[
    ((monthBtc_df['delta'] >= 0.5) & (monthBtc_df['delta'] <= 0.6)) |
    ((monthBtc_df['delta'] <= -0.45) & (monthBtc_df['delta'] >= -0.55))] #updated delta for put options
    print("Length of ATMs: ", len(delta_df))

    adjusted_df = delta_df.copy()
    adjusted_df['timestamp'] = pd.to_datetime(adjusted_df['timestamp'], unit='us')
    # Sort the DataFrame by the 'timestamp' column
    adjusted_df = adjusted_df.sort_values(by='timestamp')
    print(adjusted_df[["last_price"]].head())
    unique_price_df = adjusted_df.drop_duplicates(subset=['bid_price', 'ask_price'], keep='first')

    print("Length of Unique price: ", len(unique_price_df))

    # Convert 'local_timestamp' and 'expiration' columns from ms to date format
    unique_price_df_format = unique_price_df.copy()
    unique_price_df_format['local_timestamp'] = pd.to_datetime(unique_price_df['local_timestamp'], unit='us')
    unique_price_df_format['expiration'] = pd.to_datetime(unique_price_df['expiration'], unit='us')

    #save file
    save_file = f"datasets/Formatted 2023/{monthN}.csv"
    unique_price_df_format.to_csv(save_file, index=False)
    i += 1
    print("The value of i is now: ", i)

    


print("Job Done")


