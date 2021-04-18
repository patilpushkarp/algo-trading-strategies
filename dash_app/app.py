# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests
from datetime import date, datetime

# external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css', dbc.themes.BOOTSTRAP]
external_stylesheets = [dbc.themes.BOOTSTRAP]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

stocks = pd.read_csv("supporting_files/bse_stocks.csv")

app.layout = html.Div(style={'backgroundColor': "#111111"}, children=[
    html.H1(children='MACD Evaluator', 
            style={
            'textAlign': 'center',
            'color': "#7FDBFF",
            'padding': 30
        }),

    dbc.Row([
        dbc.Col([
            html.Label('STOCK', style={
            'color': "#7FDBFF"
        }),
            dcc.Dropdown(
                id='stock-name',
                options=[dict(label=row["STOCK"], value=row["CODE"]) for _, row in stocks.iterrows()],
                value='BOM532540'
            )
        ], width=8, align="center", style={"padding":60}),
        dbc.Col([
            html.Label('START DATE', style={
            'color': "#7FDBFF"
        }),
            html.Br(),
            dcc.DatePickerSingle(
                id='start-date',
                min_date_allowed=date(2010, 1, 1),
                max_date_allowed=datetime.today(),
                initial_visible_month=datetime.today(),
                date=date(2020, 1, 1)
            ),
        ], width=4, align="center", style={"padding":60})
    ]),

    dcc.Graph(
        id='deals-graph',
    )
])

@app.callback(
    Output('deals-graph', 'figure'),
    [Input('start-date', 'date'), 
     Input('stock-name', 'value')])
def deals_decision_maker(start_date, stock):
    response = get_stock_data(stock)
    print("Data Fetched")
    df = pd.DataFrame(columns=response["dataset"]["column_names"], data=response["dataset"]["data"])
    df = df[["Date", "Open", "High", "Low", "Close"]]
    print("Data subset done")
    df["MA12"] = df["Close"].ewm(span=12, adjust=False).mean()
    print("Calculating 12 days moving average")
    df["MA26"] = df["Close"].ewm(span=26, adjust=False).mean()
    print("Calculated 26 days moving average")
    df["MACD"] = df["MA26"] - df["MA12"]
    print("Calculated MACD")
    df["signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    print("Calculated signal")
    df["move"] = df["MACD"]>df["signal"]
    df["move"] = df["move"].apply(lambda x: float(x))
    df["positions"] = df["move"].diff()
    print("Calculated decisions")
    df["Date"] = pd.to_datetime(df["Date"])
    rev_df = df[df["Date"]>start_date]
    rev_df.sort_values("Date", ascending=True, inplace=True)
    print("Data selected after starting date")
    buy_data, sell_data, total_gain, actions = deal_stocks(rev_df)
    buy_df = pd.DataFrame(columns=["Date", "Close"], data=buy_data)
    sell_df = pd.DataFrame(columns=["Date", "Close"], data=sell_data)
    close_chart = go.Scatter(x=rev_df["Date"], y=rev_df["Close"], mode="lines")
    buy_chart = go.Scatter(x=buy_df["Date"], y=buy_df["Close"], mode="markers", marker_symbol="triangle-up", marker=dict(size=20, color="red"))
    sell_chart = go.Scatter(x=sell_df["Date"], y=sell_df["Close"], mode="markers", marker_symbol="triangle-down", marker=dict(size=20, color="green"))
    fig = go.Figure(data=[close_chart, buy_chart, sell_chart])
    # fig.update_layout(width=1200)
    return fig

def get_stock_data(index_code):
    url = f"https://www.quandl.com/api/v3/datasets/BSE/{index_code}?api_key=JVU4wxLxNHFtSRjCvezu"
    response = requests.get(url=url).json()
    return response

def deal_stocks(df, initial_money=50000, max_buy=1, max_sell=1):
    """Function to buy or sell based on the decision column i.e. positions
    
    Arguments:
    df -> Input dataframe containing the stock data
    initial_money -> Amount of money we want to put
    max_buy -> Maximum amount of shares we want to buy
    max_sell -> Maximum amount of shares we want to sell
    """
    money = initial_money
    sell_days = []
    buy_days = []
    shares_count = 0
    actions = []

    def buy(day, money, shares_count):
        date = day["Date"]
        close = day["Close"]
        shares = money // day["Close"]

        if shares < 1:
            actions.append(f"Date: {date}: Total balance: {money}, not enough money to buy {shares} shares with unit price of {close}")
        else:
            if shares > max_buy:
                units = max_buy
            else:
                units = shares

            money = money - (units*day["Close"])
            shares_count = shares_count + units
            actions.append(f"Date {date}: Buy {units} units of shares at a price of {close}, total balance is {money}")
            buy_days.append([date, close])
        return money, shares_count

    def sell(day, money, shares_count):
        date = day["Date"]
        close = day["Close"]
        if shares_count == 0:
            actions.append(f"Date {date}: Cannot sell anything as available shares is 0")
        else:
            if shares_count > max_sell:
                units = max_sell
            else:
                units = shares_count
            money = money + (units*day["Close"])
            shares_count = shares_count - units
            actions.append(f"Date {date}: Sell {units} units of shares at a price of {close}, total balance is {money}")
            sell_days.append([date, close])
        return money, shares_count

    for index, row in df.iterrows():
        state = row["positions"]
        if state == 1.0:
            money, shares_count = buy(row, money, shares_count)
        elif state == -1.0:
            money, shares_count = sell(row, money, shares_count)

    total_gains = initial_money - money
    return buy_days, sell_days, total_gains, actions

if __name__ == '__main__':
    app.run_server(debug=True)