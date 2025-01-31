"""
APIs for instruments
https://developer.tdameritrade.com/instruments/apis
"""
import requests
from modules import universe
from apis import utilities


def searchInstruments(symbol, projection):
    return utilities.apiResponseHandler(requests.get('https://api.tdameritrade.com/v1/instruments',
                                                     params={'symbol': symbol, 'projection': projection},
                                                     headers={'Authorization': 'Bearer ' + universe.tokens.accessToken}))


"""
Options for projection
symbol-search: Retrieve instrument data of a specific symbol or cusip
symbol-regex: Retrieve instrument data for all symbols matching regex. Example: symbol=XYZ.* will return all symbols beginning with XYZ
desc-search: Retrieve instrument data for instruments whose description contains the word supplied. Example: symbol=FakeCompany will return all instruments with FakeCompany in the description.
desc-regex: Search description with full regex support. Example: symbol=XYZ.[A-C] returns all instruments whose descriptions contain a word beginning with XYZ followed by a character A through C.
fundamental: Returns fundamental data for a single instrument specified by exact symbol.'
"""


def getInstrument(ticker):
    return utilities.apiResponseHandler(requests.get('https://api.tdameritrade.com/v1/instruments/' + ticker,
                                                     headers={'Authorization': 'Bearer ' + universe.tokens.accessToken}))
