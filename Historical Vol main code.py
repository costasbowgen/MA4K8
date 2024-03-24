import ccxt
import sys
import math
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm
from scipy.optimize import newton
from matplotlib.lines import Line2D
from matplotlib.dates import DayLocator, DateFormatter
from tabulate import tabulate


binance = ccxt.binance()

#FUNCTIONS

def FetchData(symbol, timeframe, points, start):
    """
    Example of inputs:
    symbol = "BTC/USDT"
    timeframe = "1d"
    limit = 365
    start_date = "2021-01-01"
    """
    #convert start_date to timestamp

    since =  int(datetime.timestamp(datetime.strptime(start, "%Y-%m-%d")) * 1000)
    #fetch data

    bars = binance.fetch_ohlcv(symbol, timeframe = timeframe, since = since, limit = points)
    df = pd.DataFrame(bars, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit= "ms")

    return df

def HistoricalVolCalc(ClosePrice, timestamp):
    #Methods follow from Appendix B of "Options Pricing and Volatility"
    #Calculating given time-frame STD
    
    DailyPercentChange = ClosePrice.pct_change() +1
    logDPC = np.log(DailyPercentChange)
    logMean = logDPC.mean()
    logStd = logDPC.std()

    #Calculating Annualised Log Std
    
    time_diff = timestamp.diff().dt.days
    time_diff = time_diff.iloc[1:].mean()  # Skip the first element and calculate the mean
    #if statement for hourly volatility checking 
    if time_diff == 0:
        time_diff = 1/24
    else:
        pass
    
    annualLogStd = (365/time_diff)**0.5 * logStd


    #checked on statista and is correct method got same answer
    #https://www.statista.com/chart/27577/cryptocurrency-volatility-dmo/
    
    return annualLogStd


    

def BlackScholes(spot_price, strike_price, time_to_expiration, volatility, risk_free_rate, CallorPut):

    #Calculate the theoretical price of a call and put option using Black-Scholes Model
    #As stated in "Option Pricing and Volatility"
    
    d1 = (np.log(spot_price / strike_price) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiration) / (volatility * np.sqrt(time_to_expiration))
    d2 = d1 - volatility * np.sqrt(time_to_expiration)
    if CallorPut == "call":
        

        option_value = spot_price * norm.cdf(d1) - strike_price * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(d2)
    elif CallorPut == "put":
        option_value = strike_price * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(-d2) - spot_price * norm.cdf(-d1)
    else:
        print("Error in BlackScholes")
        sys.exit()
    
    return option_value

def PutCallParity(option_price, spot_price, strike_price, time_to_expiration, risk_free_rate, CallorPut):
    
    #Calculates price of put option given a call option
    if CallorPut == "put":
    
        put_option_price = option_price + (strike_price / (1 + risk_free_rate)**time_to_expiration) - spot_price
    
        return put_option_price
    else:
        call_option_price = option_price + spot_price - (strike_price / (1 + risk_free_rate) ** time_to_expiration)

        return call_option_price

def BidAsk(spot_price, strike_price, time_to_expiration, volatility, risk_free_rate, CallorPut, spread):

    #Creating some function of volatility to create different buy and sells that are still competitive in today's market.
    
    BuyVol = volatility - spread/2
    SellVol = volatility + spread/2 #maybe just spread
    TheoryCallBuyPrice = BlackScholes(spot_price, strike_price, time_to_expiration, BuyVol, risk_free_rate, "call")
    TheoryPutBuyPrice = PutCallParity(TheoryCallBuyPrice, spot_price, strike_price, time_to_expiration, risk_free_rate, "put")
    TheoryCallSellPrice = BlackScholes(spot_price, strike_price, time_to_expiration, SellVol, risk_free_rate, "call")
    TheoryPutSellPrice = PutCallParity(TheoryCallSellPrice, spot_price, strike_price, time_to_expiration, risk_free_rate, "put")


    if CallorPut == "call":
        return TheoryCallBuyPrice, TheoryCallSellPrice
    elif CallorPut == "put":
        return TheoryPutBuyPrice, TheoryPutSellPrice
    else:
        print("Error with CallorPut input.")
    
    


def ImpliedVolatility(option_price, spot, strike, T, vol_guess, r, CallorPut):
    if CallorPut == "call":
    
        def f(vol_guess):
            return BlackScholes(spot, strike, T, vol_guess, r, "call") - option_price
    else:
        call_price = PutCallParity(option_price, spot, strike, T, r, "call")
        #print("PutcallParity says: ", call_price)
        if call_price < 0:
            return "Error"
        else:
            pass

        def f(vol_guess):
            return BlackScholes(spot, strike, T, vol_guess, r, "call") - call_price

        
    #print("working on a: ", CallorPut)
    #print("Details: ", option_price, spot, strike, T, vol_guess, r, CallorPut)
    try:
        implied_volatility = newton(f, vol_guess)
        #print("Implied vol: ", implied_volatility)
        return implied_volatility
    except RuntimeError as e:
        #print(f"Error: {e}")
        #print("working on a: ", CallorPut)
        #print("Details: ", option_price, spot, strike, T, vol_guess, r, CallorPut)
        return "Error"  # or any default value or behavior you prefer

def TimeMinPeriods(timestamp):
    #for no.1 of 15 minute periods    
    timestamp_string = timestamp
    timestamp_format = '%Y-%m-%d %H:%M:%S.%f'

    # Parse the timestamp string
    timestamp = datetime.strptime(timestamp_string, timestamp_format)

    # Calculate total minutes from midnight
    total_minutes = timestamp.hour * 60 + timestamp.minute

    # Calculate the number of 15-minute periods
    periods_of_5_minutes = total_minutes // 5

    return periods_of_5_minutes



            
            

def HistoricalVolTrading(inputYear, inputMonth, spread, longMax, shortMax):
    inputMonthList = ["01","02","03","04","05","06","07","08","09","10","11","12"]
    if inputMonth == "01":
        preMonthYear = str(int(inputYear)-1)
        preMonth = "12"
    else:
        index = inputMonthList.index(inputMonth)
        preMonth = inputMonthList[index-1]
        preMonthYear = inputYear
    yearStamp = f"{inputYear}-{inputMonth}-01"
    preMonthStamp = f"{preMonthYear}-{preMonth}-01"
        
    file_path = f"datasets/Formatted {inputYear}/{inputMonth}.csv"
    optionData = pd.read_csv(file_path)
    options = []
    BuyList = []
    SellList = []
    currentCallPosition = 0
    currentPutPosition = 0
    i = 0
    dayVolData = FetchData("BTC/USDT", "1d", 30, preMonthStamp)
    volatility = HistoricalVolCalc(dayVolData["Close"], dayVolData["Timestamp"])
    DayPrice = FetchData("BTC/USDT", "5m", 500, yearStamp)
    for i in range(len(optionData)):

        formattedTimestamp = TimeMinPeriods(optionData["timestamp"][i])


        strike = float(optionData.iloc[i]["strike_price"])
        expiration = (float(optionData.iloc[i]["expiration"][8:10]) - 1)/365
        iDelta = float(optionData.iloc[i]["delta"])
        #iBidIV = float(optionData.iloc[i]["bid_iv"])
        #iAskIV = float(optionData.iloc[i]["ask_iv"])         

        expirationDay = (int(optionData.iloc[i]["expiration"][8:10]) - 1)
        CallorPut = optionData.iloc[i]["type"]
        spot = float(DayPrice.iloc[formattedTimestamp]["Close"])
        marketBidPrice = optionData.iloc[i]["bid_price"] * spot
        marketAskPrice = optionData.iloc[i]["ask_price"] * spot


        
        if expiration < 0.0028 or math.isnan(marketBidPrice) or math.isnan(marketAskPrice):
            continue #to skip same day expirations
        

        AskimpliedVol = ImpliedVolatility(marketAskPrice, spot, strike, expiration, volatility, RFR, CallorPut)
        BidimpliedVol = ImpliedVolatility(marketBidPrice, spot, strike, expiration, volatility, RFR, CallorPut)
        if AskimpliedVol == "Error" or BidimpliedVol == "Error":
            continue
        

        #print("My Black Scholes Inputs: \n Strike: ", strike, "\n Exp", expiration, "\n Vol: ", volatility)
        
        if CallorPut == "call":
            MyBidPrice, MyAskPrice = BidAsk(spot, strike, expiration, volatility, RFR, CallorPut, spread)
            MyOptionPrice = BlackScholes(spot, strike, expiration, volatility, RFR, CallorPut)
        else:
            MyBidPrice, MyAskPrice = BidAsk(spot, strike, expiration, volatility, RFR, CallorPut, spread)
            callPrice = BlackScholes(spot, strike, expiration, volatility, RFR, CallorPut)
            MyOptionPrice = PutCallParity(callPrice,spot, strike, expiration, RFR, "put")

        
        if CallorPut == "call":
            if marketBidPrice > MyAskPrice and currentCallPosition > -shortMax:
                order = [CallorPut, expirationDay, strike, marketBidPrice, iDelta, 100*BidimpliedVol, volatility, "Sell"]
                #create sell order
                SellList.append(order)
                #print("Market Bid Price: ",marketBidPrice," and my Ask Price: ", MyAskPrice)
                #print("Sell order")
                currentCallPosition -= 1
            elif marketAskPrice < MyBidPrice and currentCallPosition < longMax:
                #create buy order
                order = [CallorPut, expirationDay, strike, marketAskPrice, iDelta, 100*AskimpliedVol, volatility, "Buy"]
                #print("Market ask Price: ",marketAskPrice," and my bid Price: ", MyBidPrice)
                #print("My implied vol: ", AskimpliedVol)
                BuyList.append(order)
                #print("Buy order")
                currentCallPosition += 1
                if AskimpliedVol > volatility:
                    print("WHY ARE YOU BUYING")
        elif CallorPut == "put":
            if marketBidPrice > MyAskPrice and currentPutPosition > -shortMax:
                order = [CallorPut, expirationDay, strike, marketBidPrice, iDelta, 100*BidimpliedVol, volatility, "Sell"]
                #create sell order
                SellList.append(order)
                #print("Market Bid Price: ",marketBidPrice," and my Ask Price: ", MyAskPrice)
                #print("Sell order")
                currentPutPosition -= 1
            elif marketAskPrice < MyBidPrice and currentPutPosition < longMax:
                #create buy order
                order = [CallorPut, expirationDay, strike, marketAskPrice, iDelta, 100*AskimpliedVol, volatility, "Buy"]
                #print("Market ask Price: ",marketAskPrice," and my bid Price: ", MyBidPrice)
                #print("My implied vol: ", AskimpliedVol)
                BuyList.append(order)
                #print("Buy order")
                currentPutPosition += 1
                if AskimpliedVol > volatility:
                    print("WHY ARE YOU BUYING")
        else:
            pass
    

    profit, MoneyMakers, MoneyLosers = ProfitLoss(BuyList, SellList, yearStamp)
    #print("Overall P+L is: ", profit)

    return profit, MoneyMakers, MoneyLosers

def ImpliedVolTrading(inputYear, inputMonth, spread, longMax, shortMax, deltaTrading):
    inputMonthList = ["01","02","03","04","05","06","07","08","09","10","11","12"]
    if inputMonth == "01":
        preMonthYear = str(int(inputYear)-1)
        preMonth = "12"
    else:
        index = inputMonthList.index(inputMonth)
        preMonth = inputMonthList[index-1]
        preMonthYear = inputYear
    yearStamp = f"{inputYear}-{inputMonth}-01"
    preMonthStamp = f"{preMonthYear}-{preMonth}-01"
        
    file_path = f"datasets/Formatted {inputYear}/{inputMonth}.csv"
    optionData = pd.read_csv(file_path)
    volDataByExpiry = []
    options = []
    BuyList = []
    SellList = []
    currentCallPosition = 0
    currentPutPosition = 0
    i = 0
    dayVolData = FetchData("BTC/USDT", "1d", 30, preMonthStamp)
    HistVol = HistoricalVolCalc(dayVolData["Close"], dayVolData["Timestamp"])
    DayPrice = FetchData("BTC/USDT", "5m", 500, yearStamp)
    for i in range(len(optionData)):

        formattedTimestamp = TimeMinPeriods(optionData["timestamp"][i])


        strike = float(optionData.iloc[i]["strike_price"])
        expiration = (float(optionData.iloc[i]["expiration"][8:10]) - 1)/365
        iDelta = float(optionData.iloc[i]["delta"])
        #iBidIV = float(optionData.iloc[i]["bid_iv"])
        #iAskIV = float(optionData.iloc[i]["ask_iv"])         

        expirationDay = (int(optionData.iloc[i]["expiration"][8:10]) - 1)
        CallorPut = optionData.iloc[i]["type"]
        spot = float(DayPrice.iloc[formattedTimestamp]["Close"])
        marketBidPrice = optionData.iloc[i]["bid_price"] * spot
        marketAskPrice = optionData.iloc[i]["ask_price"] * spot


        
        if expiration < 0.0028 or math.isnan(marketBidPrice) or math.isnan(marketAskPrice):
            continue #to skip same day expirations
        

        AskimpliedVol = ImpliedVolatility(marketAskPrice, spot, strike, expiration, HistVol, RFR, CallorPut)
        BidimpliedVol = ImpliedVolatility(marketBidPrice, spot, strike, expiration, HistVol, RFR, CallorPut)
        if AskimpliedVol == "Error" or BidimpliedVol == "Error":
            continue
        MarketImpliedVol = (AskimpliedVol + BidimpliedVol)/2
        #adjusting implied volatility
        found = False
        for entry in volDataByExpiry:
            if entry[0] == expirationDay:
                entry[2] += 1
                volatility = ((entry[2]-1)/entry[2]) * entry[1] + (1/entry[2]) * MarketImpliedVol
                entry[1] = volatility
                found = True
                break
        if not found:
            volatility = HistVol * MarketImpliedVol
            volDataByExpiry.append([expirationDay, volatility, 1])
                
        

        #print("My Black Scholes Inputs: \n Strike: ", strike, "\n Exp", expiration, "\n Vol: ", volatility)
        
        if CallorPut == "call":
            MyBidPrice, MyAskPrice = BidAsk(spot, strike, expiration, volatility, RFR, CallorPut, spread)
            MyOptionPrice = BlackScholes(spot, strike, expiration, volatility, RFR, CallorPut)
        else:
            MyBidPrice, MyAskPrice = BidAsk(spot, strike, expiration, volatility, RFR, CallorPut, spread)
            callPrice = BlackScholes(spot, strike, expiration, volatility, RFR, CallorPut)
            MyOptionPrice = PutCallParity(callPrice,spot, strike, expiration, RFR, "put")

        
        if CallorPut == "call":
            if marketBidPrice > MyAskPrice and currentCallPosition > -shortMax:
                order = [CallorPut, expirationDay, strike, marketBidPrice, iDelta, 100*BidimpliedVol, volatility, "Sell"]
                #create sell order
                SellList.append(order)
                #print("Market Bid Price: ",marketBidPrice," and my Ask Price: ", MyAskPrice)
                #print("Sell order")
                currentCallPosition -= 1
            elif marketAskPrice < MyBidPrice and currentCallPosition < longMax:
                #create buy order
                order = [CallorPut, expirationDay, strike, marketAskPrice, iDelta, 100*AskimpliedVol, volatility, "Buy"]
                #print("Market ask Price: ",marketAskPrice," and my bid Price: ", MyBidPrice)
                #print("My implied vol: ", AskimpliedVol)
                BuyList.append(order)
                #print("Buy order")
                currentCallPosition += 1
                if AskimpliedVol > volatility:
                    print("WHY ARE YOU BUYING")
        elif CallorPut == "put":
            if marketBidPrice > MyAskPrice and currentPutPosition > -shortMax:
                order = [CallorPut, expirationDay, strike, marketBidPrice, iDelta, 100*BidimpliedVol, volatility, "Sell"]
                #create sell order
                SellList.append(order)
                #print("Market Bid Price: ",marketBidPrice," and my Ask Price: ", MyAskPrice)
                #print("Sell order")
                currentPutPosition -= 1
            elif marketAskPrice < MyBidPrice and currentPutPosition < longMax:
                #create buy order
                order = [CallorPut, expirationDay, strike, marketAskPrice, iDelta, 100*AskimpliedVol, volatility, "Buy"]
                #print("Market ask Price: ",marketAskPrice," and my bid Price: ", MyBidPrice)
                #print("My implied vol: ", AskimpliedVol)
                BuyList.append(order)
                #print("Buy order")
                currentPutPosition += 1
                if AskimpliedVol > volatility:
                    print("WHY ARE YOU BUYING")
        else:
            pass
    #("Buy list pre-delta trading: ", BuyList[0])
    if deltaTrading == True:
        deltaProfit = MakeDeltaNeutral(BuyList,SellList, inputYear, inputMonth)
    else:
        deltaProfit = 0
        
        
    
    #print("Buy list: ", BuyList[0])
    optionProfit, MoneyMakers, MoneyLosers = ProfitLoss(BuyList, SellList, yearStamp)
    profit = optionProfit + deltaProfit
    
    print("Overall P+L is: ", profit)
    #print(f"Vol data by expiry: {volDataByExpiry}")
    
    return profit, MoneyMakers, MoneyLosers, volDataByExpiry

def GroupByExpiration(inputList):
    expiration_groups = {}
    for entry in inputList:
        expiration_day = entry[1]  
        if expiration_day not in expiration_groups:
            expiration_groups[expiration_day] = []  
        expiration_groups[expiration_day].append(entry)  
    return expiration_groups

def DeltaCalc(option_type, spot_price, strike_price, time_to_expiry, risk_free_rate, volatility):
    time_to_expiry = time_to_expiry/365

    d1 = (math.log(spot_price / strike_price) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
    
    if option_type == 'call':
        delta = math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d1)
    elif option_type == 'put':
        delta = -math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d1)
    else:
        raise ValueError("Invalid option type. Must be 'call' or 'put'.")
    
    return delta


def MakeDeltaNeutral(BuyList, SellList, year, month):
    dailyPrices = FetchData("BTC/USDT", "1d", 32, f"{year}-{month}-01")
    deltaProfit = 0
    expBuyList = GroupByExpiration(BuyList)
    for key in expBuyList:
        for entry in expBuyList[key]:
            entry.append(deltaProfit)
            
    expSellList = GroupByExpiration(SellList)
    for key in expSellList:
        for entry in expSellList[key]:
            entry.append(deltaProfit)
    
    
    deltaSumBuy = 0
    deltaSumSell = 0
    overall_Money = 0
    i = 0
    #print("The buy list: ")
    #print(expBuyList)

    while i < 32:
        for key in sorted(expBuyList.keys()):
            if i > key:
                pass
            elif i == key:
                counter =0
                for entry in expBuyList[key]:
                    #neutralise your delta positions
                    change_delta = -entry[4] #need to cancel out the delta
                    Money_change = change_delta*dailyPrices["Open"][i] 
                    #print("Final day, and position is worth: ", current_position)
                    entry[8] += Money_change
                    #print("We sell our position as option has expired, so we don't need to neutralise it. Final pandl: ", entry[8])
                    deltaSumBuy += entry[8]
                    if entry[0] == "call" and entry[2] < dailyPrices["Open"][i]:
                        overall_profit = entry[8] + (dailyPrices["Open"][i] - entry[2]) - entry[3]
                    elif entry[0] == "put" and entry[2] > dailyPrices["Open"][i]:
                        overall_profit = entry[8] + (entry[2] - dailyPrices["Open"][i]) - entry[3]
                    else:
                        overall_profit = entry[8] - entry[3]
                    overall_Money += overall_profit
                    if counter == 0 and key == 30:
                        counter = 1
                        #print(f"Final day, delta was {entry[4]} and money from delta neutral positions is {entry[8]}. Bitcoin is worth:", dailyPrices["Open"][i] )
                        
            else:
                
                #print(f"Entries with key {key}:")
                counter = 0
                for entry in expBuyList[key]:
                    if i > 0:
                        old_delta = entry[4]
                        new_delta = DeltaCalc(entry[0], dailyPrices["Open"][i], entry[2], entry[1], RFR, entry[6])
                        change_delta = new_delta - old_delta
                        Money_change = change_delta * dailyPrices["Open"][i]
                        entry[8] += Money_change
                        entry[4] = new_delta
                        if counter == 0 and key == 30:
                            counter = 1
                            #print(f"It is day {i}, the change in delta is {change_delta}, delta is now {new_delta} so our change in bank money is {Money_change}, and our total money from this trade is {entry[8]}")
                        #print(f"With new price, current position is now worth {current_position}")
                    else:
                        delta = DeltaCalc(entry[0], dailyPrices["Open"][i], entry[2], entry[1], RFR, entry[6])
                        entry[4] = delta
                        entry[8] = delta*dailyPrices["Open"][i] #e.g. assume delta 0.5, then sell 0.5 bitcoin, so bank balance positive
                        #print(f"Price of bitcoin is", dailyPrices["Open"][i], f"Delta is {delta}, i = 0, so we are selling (buying if -) {positionWanted} worth of bitcoin. . We are currently {entry[8]} in terms of pandl.")
                        if counter == 0 and key == 30:
                            counter = 1
                            #print(f"It is day 0, delta is {delta}, so our bank poisiton is {entry[8]}")
        i += 1
    #print(f"The overall profit of buying and selling to neutralise delta is: {deltaSumBuy}")
    i = 0    
    while i < 32:
        for key in sorted(expSellList.keys()):
            if i > key:
                pass
            elif i == key:
                for entry in expSellList[key]:
                    #neutralise your delta positions
                    change_delta = -entry[4] #need to cancel out the delta
                    Money_change = change_delta*dailyPrices["Open"][i] 
                    #print("Final day, and position is worth: ", current_position)
                    entry[8] += Money_change
                    #print("We sell our position as option has expired, so we don't need to neutralise it. Final pandl: ", entry[8])
                    deltaSumBuy += entry[8]
                    if entry[0] == "call" and entry[2] < dailyPrices["Open"][i]:
                        overall_profit = entry[8] -((dailyPrices["Open"][i] - entry[2]) - entry[3])
                    elif entry[0] == "put" and entry[2] > dailyPrices["Open"][i]:
                        overall_profit = entry[8] -((entry[2] - dailyPrices["Open"][i]) - entry[3])
                    else:
                        overall_profit = entry[8] + entry[3]
                    overall_Money += overall_profit
                    

            else:
                
                #print(f"Entries with key {key}:")
                for entry in expSellList[key]:
                    if i > 0:
                        old_delta = entry[4]
                        new_delta = -DeltaCalc(entry[0], dailyPrices["Open"][i], entry[2], entry[1], RFR, entry[6])
                        change_delta = new_delta - old_delta
                        Money_change = change_delta * dailyPrices["Open"][i]
                        entry[8] += Money_change
                        entry[4] = new_delta
                        
                        #print(f"With new price, current position is now worth {current_position}")
                        
                        
                    else:
                        delta = DeltaCalc(entry[0], dailyPrices["Open"][i], entry[2], entry[1], RFR, entry[6])
                        entry[4] = -delta
                        entry[8] = -delta*dailyPrices["Open"][i] #e.g. assmume delta = 0.5, we sold it, so we have -0.5 delta, so buy BTC to neutralise, so negative bank
                        #print(f"Price of bitcoin is", dailyPrices["Open"][i], f" i = 0 so we are buying {positionWanted} worth of bitcoin. Delta is {delta}. We are currently down {entry[8]} in terms of pandl.")
                
        i += 1
    #print(f"The overall profit of buying and selling to neutralise delta is: {deltaSumSell}")
    #print(expBuyList)
    #print(expSellList)
    deltaProfit = deltaSumBuy + deltaSumSell
    #print(f"The delta profit is: {deltaProfit}") 
    #print(f"The overall money of month should be {overall_Money}")
    
    return deltaProfit
    
    
    
    

def ProfitLoss(BuyList, SellList, month):
    profit = 0
    MoneyMakers = []
    MoneyLosers = []
    expiryPrice = FetchData("BTC/USDT", "1d", 31, month)
    for item in BuyList:
        itemDetails = item
        expiryDayPrice = expiryPrice["Close"].iloc[(item[1])]
        if item[0] == "call":
            if expiryDayPrice > item[2]:
                profChange = ((expiryDayPrice - item[2]) - item[3])
                itemDetails.append(profChange)
                if profChange >= 0:
                    #made money long call
                    MoneyMakers.append(itemDetails)
                    profit += profChange
                   # print("Made money long call: +", profChange)
                else:
                    #lost money long call and exercised
                    MoneyLosers.append(itemDetails)
                    profit += profChange
                    #print("Lost money long call: ", profChange)
            else:
                profChange = -item[3]
                itemDetails.append(profChange)
                #lost money long call
                MoneyLosers.append(itemDetails)
                profit += profChange
                #print("Lost money long call: ", profChange)
        elif item[0] == "put":
            if expiryDayPrice < item[2]:
                profChange = ((item[2] - expiryDayPrice) - item[3])
                itemDetails.append(profChange)
                if profChange >= 0:
                    #made money long put
                    MoneyMakers.append(itemDetails)
                    #print("Exercised Put: ", profChange)
                    profit += profChange
                else:
                    #lost money and exercised long put
                    MoneyLosers.append(itemDetails)
                    #print("Exercised Put: ", profChange)
                    profit += profChange
                    
            else:
                profChange = -item[3]
                itemDetails.append(profChange)
                #lost money long put
                MoneyLosers.append(itemDetails)
                #print("Lost money long Put: ", profChange)
                profit += profChange
        #print("Price on expiry day was: ", expiryDayPrice, " and details: ", item)
        #print("Profit = ", profit)

    for item in SellList:
        itemDetails = item
        expiryDayPrice = expiryPrice["Close"].iloc[(item[1])]
        if item[0] == "call":
            if expiryDayPrice > item[2]:
                profChange = -((expiryDayPrice - item[2]) - item[3])
                itemDetails.append(profChange)
                if profChange < 0:
                    #lost money short call
                    profit += profChange
                    #print("Lost money short call : ", profChange)
                    MoneyLosers.append(itemDetails)
                else:
                    #made money after expiration short call
                    profit += profChange
                   # print("A short call was exercised, we made : ", profChange)
                    MoneyMakers.append(itemDetails)
                    
            else:
                #made money short call
                profChange = item[3]
                itemDetails.append(profChange)
                profit += profChange
                #print("Made money short call: ", profChange)
                MoneyMakers.append(itemDetails)
        elif item[0] == "put":
            if expiryDayPrice < item[2]:
                profChange = -((item[2] - expiryDayPrice) - item[3])
                itemDetails.append(profChange)
                if profChange < 0:
                    #lost money short put
                    #print("A short put was exercised: ", profChange)
                    profit += profChange
                    MoneyLosers.append(itemDetails)
                else:
                    #made money after having to exercise a short put
                    #print("A short put was exercised, we made: ", profChange)
                    profit += profChange
                    MoneyMakers.append(itemDetails)
            else:
                profChange = item[3]
                itemDetails.append(profChange)
                #made money short put
                #print("Made money short put: ", profChange) 
                profit += profChange
                MoneyMakers.append(itemDetails)
        #print("Price on expiry day was: ", expiryDayPrice, " and details: ", item)
        #print("Profit = ", profit)
    
    

    return profit, MoneyMakers, MoneyLosers


def ProfitData(spread, longPositionMax, shortPositionMax, TradeType, deltaTrading):
    inputYear = ["2019", "2020", "2021", "2022", "2023"]#add 2022 and 2023 soon EDIT HERE IF TAKING TOO LONG
    inputMonth = ["01","02","03","04","05","06","07","08","09","10","11","12"]

    #inputYearChoice = "2021"
    #inputMonthChoice = "12"
    profit_table = {}
    profit_list = []
    total_profit = 0
    profit_2019 = 0
    profit_2020 = 0
    profit_2021 = 0
    profit_2022 = 0
    profit_2023 = 0

    for year in inputYear:
        if year not in profit_table:
            profit_table[year] = {}

        for month in inputMonth:
            if (year == "2019" and int(month) < 4) or int(month) > 12:
                continue
            
            if TradeType == "Historical":
                profit, MoneyMakers, MoneyLosers = HistoricalVolTrading(year, month, spread, longPositionMax, shortPositionMax)
            elif TradeType == "Implied":
                profit, MoneyMakers, MoneyLosers, _ = ImpliedVolTrading(year, month, spread, longPositionMax, shortPositionMax, deltaTrading)
            elif TradeType == "DeltaNeutral":
                #fill
                pass
            else:
                print("Error in Trade type.")


            profit = "{:.2f}".format(profit)
            profit = float(profit)
            profit_table[year][month] = profit
            profit_list.append(profit)
            print(f"Profit from {month}-{year} was: ", profit)
            total_profit += profit
            if year == "2019":
                profit_2019 += profit
            elif year == "2020":
                profit_2020 += profit
            elif year == "2021":
                profit_2021 += profit
            elif year == "2022":
                profit_2022 += profit
            elif year == "2023":
                profit_2023 += profit

    yearlyProfits = [profit_2019, profit_2020, profit_2021, profit_2022, profit_2023]
    yearlyProfitFormat = []

    # Creating the table
    table_headers = ["Month"] + inputYear
    table_data = []

    for month in inputMonth:
        row_values = [profit_table[year].get(month, 'N/A') for year in inputYear]
        table_data.append([month] + row_values)
    for item in yearlyProfits:
        item = format(item, '.2f')
        yearlyProfitFormat.append(item)

    total_profit_row = ["Total"] + yearlyProfitFormat

    table_data.append(total_profit_row)

    # Printing the formatted table
    print("\nProfit Table:")
    formatted_table = tabulate(table_data, headers=table_headers, tablefmt="pretty")
    print(formatted_table)
    total_profit = format(total_profit, ".2f")
    # Total Profit
    print("\nTotal Profit:", total_profit)
    return table_data, profit_list


def MonthProfitGraph(inputYearChoice, inputMonthChoice, spread, longPositionMax, shortPositionMax, TradeType, deltaTrading):
    if TradeType == "Historical":
        profit, MoneyMakers, MoneyLosers = HistoricalVolTrading(inputYearChoice, inputMonthChoice, spread, longPositionMax, shortPositionMax)
    elif TradeType == "Implied":
        profit, MoneyMakers, MoneyLosers, volDataByExpiry = ImpliedVolTrading(inputYearChoice, inputMonthChoice, spread, longPositionMax, shortPositionMax, deltaTrading)
    elif TradeType == "DeltaNeutral":
        #fill
        pass
    else:
        print("Error in Trade type.")
    
    
    yearStamp = f"{inputYearChoice}-{inputMonthChoice}-01"
    print("This months profit was: ", profit)

    #MoneyMakers = [Call or put, expiration, strike, premium, delta, market vol, my vol, Buy or Sell, Profit]
    #MoneyLosers = [Call or put, expiration, strike, premium, delta, market vol, my vol, Buy or Sell, Profit]


    #PLOTS
    #---------------------------------------------------------------------------------------------------------------

    all_data = MoneyMakers + MoneyLosers
    print("Number of trades: ", len(all_data))

    if deltaTrading == True:
        for entry in all_data:
            entry.append(entry[8]+entry[9])
    
    

    fig, ax = plt.subplots()

    if TradeType == "Implied":
        volDataByExpiry_sorted = sorted(volDataByExpiry, key=lambda x: x[0])
        vol_x = [data[0] for data in volDataByExpiry_sorted]
        vol_y = [100*data[1] for data in volDataByExpiry_sorted]

        # Plotting vol data
        plt.plot(vol_x, vol_y, 'o-', color='blue', label='Volatility Level')

        # Plotting trade data
        for trade in all_data:
            trade_x = trade[1]  # day of month
            trade_y = trade[5]  # market volatility level
            
            size = abs(trade[-1])  # Absolute value of Profit
            color = 'green' if trade[-1] >= 0 else 'red'  # Green for positive Profit, red for negative
        
            # Determine marker style based on the entry type
            marker = 'o' if trade[7] == 'Buy' else 's'
            plt.scatter(trade_x, trade_y,s=size, edgecolors=color, facecolors="none", marker=marker)

        # Adding labels and title
        plt.xlabel('Day of Month')
        plt.ylabel('Volatility')
        plt.title(f'Volatility Across the Month starting ({yearStamp})')
        legend_elements = [Line2D([0], [0], marker='o', color='w', markerfacecolor='none', markeredgecolor='black', markersize=10, label='Buy'),
                           Line2D([0], [0], marker='s', color='w', markerfacecolor='none', markeredgecolor='black', markersize=10, label='Sell')]

        # Add legend
        ax.legend(handles=legend_elements)

        # Adding legend
        

        # Displaying the plot
        plt.grid(True)
        
        
            

    # Plotting different markers for 'Buy' and 'Sell' entries
    else:
        for item in all_data:
            delta = item[4]  # Delta
            y = item[5]  # Market vol
            size = abs(item[-1])  # Absolute value of Profit
            color = 'green' if item[-1] >= 0 else 'red'  # Green for positive Profit, red for negative
            
            # Determine marker style based on the entry type
            marker = 'o' if item[7] == 'Buy' else 's'  # Circle for 'Buy', square for 'Sell'
            
            ax.scatter(delta, y, s=size, edgecolors=color, facecolors='none', marker=marker)

        # Create a custom legend
        legend_elements = [Line2D([0], [0], marker='o', color='w', markerfacecolor='none', markeredgecolor='black', markersize=10, label='Buy'),
                           Line2D([0], [0], marker='s', color='w', markerfacecolor='none', markeredgecolor='black', markersize=10, label='Sell')]

        # Add legend
        ax.legend(handles=legend_elements)

        # Extract your volatility from the first entry of MoneyMakers
        your_volatility = MoneyMakers[0][-3]*100

        # Add a straight line parallel to the x-axis marking your volatility in blue
        ax.axhline(your_volatility, color='blue', linestyle='--', label='Your Volatility')

        # Set labels and title
        ax.set_xlabel('Delta')
        ax.set_ylabel('Market Volatility')
        ax.set_title(f'Volatility vs. Delta Over the Month starting ({yearStamp})')


    #FETCH DATA
    btc_data = FetchData("BTC/USDT", "2h", 360, yearStamp)

    # Plot Crypto Prices and Options
    fig, ax = plt.subplots()

    # Plot Crypto Prices
    ax.plot(btc_data["Timestamp"], btc_data["Close"], label='Bitcoin Price', color='blue')

    # Plot Call and Put Options
    legend_labels = set()  # Set to store unique legend labels

    for item in all_data:
        option_type = item[0].lower()
        expiration_days = item[1] 
        strike_price = item[2]
        action = item[7].lower()
        color = 'green' if action == 'buy' else 'red'

        # Determine marker style based on the combination of option type and action
        if option_type == 'call' and action == 'buy':
            marker = '^'
            label = 'Call Buy'
        elif option_type == 'call' and action == 'sell':
            marker = '^'
            label = 'Call Sell'
        elif option_type == 'put' and action == 'buy':
            marker = 'v'
            label = 'Put Buy'
        elif option_type == 'put' and action == 'sell':
            marker = 'v'
            label = 'Put Sell'

        # Calculate expiration date by adding expiration days to the current date
        expiration_date = datetime.strptime(yearStamp, "%Y-%m-%d") + timedelta(days=expiration_days)

        ax.scatter(expiration_date, strike_price, marker=marker, edgecolors=color, facecolors='none', label=label, s=100)

        # Add the unique label to the set
        legend_labels.add(label)

    # Set a locator to show ticks every 5 days
    ax.xaxis.set_major_locator(DayLocator(interval=3))
    ax.xaxis.set_major_formatter(DateFormatter('%d'))

    ax.set_xlabel('Day of the Month')
    ax.set_ylabel('Price (USDT) / Strike Price')
    ax.set_title(f'Bitcoin Price and Options Over the Month starting ({yearStamp})')

    # Create a custom legend with unique labels
    legend_elements = [Line2D([0], [0], marker='^', color='w', markerfacecolor='none', markeredgecolor='green', markersize=10, label='Call Buy'),
                       Line2D([0], [0], marker='^', color='w', markerfacecolor='none', markeredgecolor='red', markersize=10, label='Call Sell'),
                       Line2D([0], [0], marker='v', color='w', markerfacecolor='none', markeredgecolor='green', markersize=10, label='Put Buy'),
                       Line2D([0], [0], marker='v', color='w', markerfacecolor='none', markeredgecolor='red', markersize=10, label='Put Sell')]

    # Add the custom legend
    ax.legend(handles=legend_elements)



    # Show the plot
    plt.show()
    return

    
#END OF FUNCTIONS

#Choose your variables

RFR = 0.0242
"""Variables for ProfitData and MonthProfitGraph"""
#inputYearChoice = "2021" 
#inputMonthChoice = "10"
longPositionMax = 20
shortPositionMax = 10
spread = 0.2
TradeType = "Implied"
deltaTrading = True

#profit, MoneyMakers, MoneyLosers = ImpliedVolTrading("2020", "11", spread, longPositionMax, shortPositionMax, deltaTrading)
#print(f"The profit without delta stuff was: {profit}")

#Run the functions

dataTableImplied, profit_list = ProfitData(spread, longPositionMax, shortPositionMax, TradeType, deltaTrading)
mean_profit = np.mean(profit_list)
std_profit = np.std(profit_list)

print(f"data table implied: {dataTableImplied}")
#dataTableHist = ProfitData(spread, longPositionMax, shortPositionMax, "Historical", deltaTrading)
#print(f"data table historical: {dataTableImplied}")

# Create a new table by subtracting values from dataTableHist from dataTableImplied
print(f"The mean monthly profit was {mean_profit} and the standard deviation was {std_profit}")
result_table = []



# Print the result

inputYear = ["2019", "2020", "2021", "2022", "2023"]
table_headers = ["Month"] + inputYear
formatted_table = tabulate(result_table, headers=table_headers, tablefmt="pretty")
print(formatted_table)

inputYearChoice = "2022"
inputMonthChoice = "07" 
MonthProfitGraph(inputYearChoice, inputMonthChoice, spread, longPositionMax, shortPositionMax, TradeType, deltaTrading)



