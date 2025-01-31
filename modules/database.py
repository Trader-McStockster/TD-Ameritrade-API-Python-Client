"""
This file contains commands to access the database
Coded by Tyler Bowers
Github: https://github.com/tylerebowers/TD-Ameritrade-API-Python-Wrapper
"""

import psycopg2 as psql
import pandas as pd
from datetime import datetime
from modules import universe
from sqlalchemy import create_engine, text


def DBConnect():
    try:
        universe.database.connection = psql.connect(
            host=universe.credentials.postgresqlHost,
            user=universe.credentials.postgresqlUsername,
            password=universe.credentials.postgresqlPassword,
            database=universe.credentials.postgresqlDatabase
        )
        universe.database.cursor = universe.database.connection.cursor()
        universe.database.engine = create_engine(
            f'postgresql+psycopg2://{universe.credentials.postgresqlUsername}:{universe.credentials.postgresqlPassword}@{universe.credentials.postgresqlHost}/{universe.credentials.postgresqlDatabase}').connect()
        universe.preferences.usingDatabase = True
    except Exception as e:
        print(e)
        universe.preferences.usingDatabase = False
        universe.terminal.error("There was a problem connecting to the database.")


def DBSetup():  # only needs to be run once, won't make any changes if database is already properly setup
    for key in universe.stream.fieldAliases:
        universe.database.cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {key}")
    universe.database.connection.commit()


def cleanTimestamp(timestamp, milliseconds=False):  # formats to epoch in seconds (or milliseconds)
    if milliseconds:
        multiplier = 1000
    else:
        multiplier = 1
    if type(timestamp) == datetime:
        return float(timestamp.timestamp() * multiplier)
    elif type(timestamp) == str or type(timestamp) == int:
        timestamp = float(timestamp)
    if timestamp < 90000000000:  # it's in seconds already
        return float(timestamp * multiplier)
    else:
        return (float(timestamp) / 1000) * multiplier


class Snapshot:  # a single moment of data for a particular ticker

    def __init__(self, service, symbol, timestamp=0, dataDict=None, fields=None, fillFromPrevious=True):
        try:
            self.symbol = symbol.upper()  # ticker
            self.service = service.upper()
            self.timestamp = cleanTimestamp(timestamp)
            self.datetime = datetime.fromtimestamp(float(self.timestamp))
            if universe.dataframes[self.service].get(f"{self.symbol}_PREVIOUS_SNAP", None) is not None and fillFromPrevious:
                self.attributes = universe.dataframes[self.service][f"{self.symbol}_PREVIOUS_SNAP"].attributes
            else:
                self.attributes = {}
            for key in dataDict:
                if key.isdigit():
                    self.attributes[key] = dataDict.get(key)
            universe.dataframes[self.service][f"{self.symbol}_PREVIOUS_SNAP"] = self
            if self.symbol is None or self.service is None or self.timestamp is None or len(self.attributes) < 1:
                universe.terminal.warning(f"There might have been a problem in creating a snapshot object for {self.symbol}.")
        except Exception as e:
            universe.terminal.error(f"There was a problem in Snapshot initializer (__init__): {e}")

    def toPrettyString(self):
        try:
            streamString = f"{self.service.upper()}.{self.symbol.upper()}; {self.datetime.strftime('%c')}"
            for attribute in self.attributes:  streamString += f", {universe.stream.fieldAliases[self.service][int(attribute)]}: {self.attributes[attribute]}"
            return streamString
        except Exception as e:
            universe.terminal.error(f"There was a problem in Snapshot toPrettyString: {e}")

    def __dict__(self, useAliases=False):
        selfDict = {"service": self.service, "symbol": self.symbol,
                    "datetime": datetime.fromtimestamp(self.attributes.get('timestamp', 0))}
        if useAliases:
            for attribute in self.attributes: selfDict[universe.stream.fieldAliases[self.service][int(attribute)]] = \
            self.attributes[attribute]
        else:
            selfDict.update(self.attributes)
        return selfDict

    def __str__(self, useAliases=False):
        return str(self.__dict__(useAliases=useAliases))

    def __get__(self, toGet):
        match toGet.lower():
            case "symbol":
                return self.symbol
            case "service":
                return self.service
            case "timestamp":
                return self.timestamp
            case "datetime":
                return datetime.fromtimestamp(self.attributes.get('timestamp', 0))
            case "all" | "dict" | "raw":
                return self.__dict__()
            case _:
                try:
                    if type(toGet) == str and toGet.isdigit():
                        return self.attributes.get(toGet)
                    if type(toGet) == int:
                        return self.attributes.get(str(toGet))
                    elif type(toGet) == str:
                        return self.attributes.get(str(universe.stream.fieldAliases.index(toGet)))
                    else:
                        return None
                except Exception as e:
                    universe.terminal.error(f"There was an issue with snapshot.get(): {e}")
                    return None


def DBCreateTable(service, keys, fields):
    if type(keys) != list: keys = [keys]
    if type(fields) != list: fields = [fields]
    try:
        for key in keys:
            universe.database.cursor.execute(
                f"SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = '{service.lower()}' AND tablename  = '{key.lower()}')")
            if bool(universe.database.cursor.fetchone()[0]):
                universe.database.cursor.execute(
                    f"ALTER TABLE {service}.{key} ADD COLUMN IF NOT EXISTS Timestamp timestamp")
                for field in fields:
                    if int(field) != 0:
                        colName = universe.stream.fieldAliases.get(service.upper())[int(field)]
                        colDatatype = universe.stream.fieldDatatypes.get(service.upper())[int(field)]
                        universe.database.cursor.execute(
                            f"ALTER TABLE {service}.{key} ADD COLUMN IF NOT EXISTS {colName} {colDatatype}")
            else:
                attributes = "(Timestamp timestamp"
                for i, field in enumerate(fields):
                    if i != 0:
                        attributes += ", "
                        attributes += universe.stream.fieldAliases.get(service.upper())[field] + " " + \
                                      universe.stream.fieldDatatypes.get(service.upper())[field]
                attributes += ")"
                universe.database.cursor.execute(f"CREATE TABLE IF NOT EXISTS {service}.{key} {attributes}")
        universe.database.commit()
    except Exception as e:
        universe.terminal.error(f"There was a problem in DBCreateTable (adding a new table to the database): {e}")
        return None


def DBAddSnapshot(snap):  # need check if database exists
    try:
        symbol = snap.symbol
        service = snap.service
        columns = f"(timestamp"
        values = f"(to_timestamp({snap.timestamp})"
        for field in snap.attributes:
            if field.isdigit():
                columns += f", {universe.stream.fieldAliases.get(service.upper())[int(field)]}"
                values += f", {snap.attributes.get(field)}"
        columns += ")"
        values += ")"
        if len(columns) > 12 and len(values) > 32 and symbol is not None:
            universe.database.cursor.execute(f"INSERT INTO {service}.{symbol} {columns} VALUES {values}")
            universe.database.connection.commit()
    except Exception as e:
        universe.terminal.error(f"There was a problem in DBAddSnapshot (adding a snapshot to the database): {e}")
        return None


def DBAddData(service, ticker, timestamp, data):  # should check if database exists
    try:
        timestamp = cleanTimestamp(timestamp)
        columns = f"(timestamp"
        values = f"(to_timestamp({timestamp})"
        for key in data:
            if key.isdigit():
                columns += ", "
                values += ", "
                columns += universe.stream.fieldAliases.get(service.upper())[int(key)]
                values += str(data.get(key))
        columns += ")"
        values += ")"
        if len(columns) > 16 and len(values) > 32: universe.database.cursor.execute(
            f"INSERT INTO {service}.{ticker} {columns} VALUES {values}")
        universe.database.connection.commit()
    except Exception as e:
        universe.terminal.error(f"There was a problem in DBAddData (adding data to the database): {e}")
        return None


def DBGetTable(service, ticker, select="*", lowerBound=None, upperBound=None, backwards=None):  # datetime or timestamps
    try:
        if backwards is not None:
            backwards = cleanTimestamp(backwards)
            lowerBound = (datetime.now().timestamp() - backwards)
            sql = f"select {select} from {service.upper()}.{ticker.upper()} where timestamp >= to_timestamp({lowerBound})"
            return pd.DataFrame(universe.database.engine.execute(text(sql)))
        if lowerBound is not None: lowerBound = cleanTimestamp(lowerBound)
        if upperBound is not None: upperBound = cleanTimestamp(upperBound)
        if lowerBound is not None and upperBound is not None:
            sql = f"select {select} from {service.upper()}.{ticker.upper()} where timestamp between to_timestamp({lowerBound}) and to_timestamp({upperBound});"
        elif lowerBound is not None:
            sql = f"select {select} from {service.upper()}.{ticker.upper()} where timestamp >= to_timestamp({lowerBound})"
        elif upperBound is not None:
            sql = f"select {select} from {service.upper()}.{ticker.upper()} where timestamp <= to_timestamp({lowerBound})"
        else:
            sql = f"select {select} from {service.upper()}.{ticker.upper()}"
        return pd.DataFrame(universe.database.engine.execute(text(sql)))
    except Exception as e:
        universe.terminal.error(f"There was a problem in DBGetTable (getting table from the database): {e}")
        return None


def DFCreateTable(service, ticker, columns):
    try:
        colNames = [("0", "timestamp")]
        for key in columns:
            if (type(key) == int or key.isdigit()) and int(key) != 0:
                colNames.append((str(key), universe.stream.fieldAliases.get(service.upper())[int(key)]))
        df = pd.DataFrame(columns=colNames)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        universe.dataframes[service.upper()][ticker.upper()] = df
    except Exception as e:
        universe.terminal.error(f"There was a problem in DFCreateTable (creating a new dataframe): {e}")
        return None


def DFGetTable(service, ticker):
    try:
        return universe.dataframes[service.upper()][ticker.upper()]
    except Exception as e:
        universe.terminal.error(f"There was a problem in DFGetTable: {e}")
        return None


def DFAddSnapshot(snap):
    try:
        symbol = snap.symbol
        service = snap.service
        df = universe.dataframes[service][symbol]
        rowToAdd = [snap.timestamp]
        for field in df.columns:
            if field[0].isdigit() and int(field[0]) != 0:
                rowToAdd.append(snap.attributes.get(field[0], None))
        if len(df.columns) == len(rowToAdd):
            df.loc[len(df.index)] = rowToAdd
        else:
            universe.terminal.error("There was a problem in DFAddSnapshot, columns mismatch")
    except Exception as e:
        universe.terminal.error(f"There was a problem in DFAddSnapshot (adding snapshot to dataframe): {e}")
        return None


def DFAddData(service, symbol, timestamp, data):
    try:
        df = universe.dataframes[service][symbol]
        rowToAdd = [cleanTimestamp(timestamp)]
        for field in df.columns:
            if field.isdigit():
                rowToAdd.append(data.get(field, None))
        df.loc[len(df.index)] = rowToAdd
    except Exception as e:
        universe.terminal.error(f"There was a problem in DFAddData (adding data to dataframe): {e}")
        return None
