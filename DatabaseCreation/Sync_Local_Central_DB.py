# Get Data from Google Sheet
import sqlite3
from sqlite3 import Error
import gspread
from google.oauth2.service_account import Credentials
import datetime
import os
import pandas
import numpy 

scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

credentials = Credentials.from_service_account_file(
    '../campaign-318908-b7f2f5f17cab.json',
    scopes=scopes
)

# gc = gspread.authorize(credentials)


def get_from_sheet(google_sheet_file_name,sheet_name):
    gc = gspread.authorize(credentials)
    
    fb_username_url_gs = gc.open(google_sheet_file_name).worksheet(sheet_name)

    # google_sheet_row_data = fb_username_url_gs.col_values(1)
    google_sheet_row_data = fb_username_url_gs.get_all_values()


    return google_sheet_row_data
    # print(google_sheet_row_data)
    # existingRow = len(google_sheet_row_data)

    # print(existingRow)


# data = get_from_sheet("Campeign 001","logs")

# print(data)
print(os.environ['COMPUTERNAME'])

def date_difference_status(sheet_date,local_server_date):
    len_last = len(sheet_date.split(' ')[1].split(':')[0])
    if len_last == 1:
        sheet_date = sheet_date[:11] + '0'+sheet_date.split(' ')[1].split(':')[0] + sheet_date[11 + 1:]
    sheet = datetime.datetime.fromisoformat(sheet_date)

    local = local_server_date.split('.')[0]

    local = datetime.datetime.fromisoformat(local)
    if sheet == local:
            return ("all_updated",local_server_date)
    elif sheet > local:
        return ("sheet_updated",sheet_date)
    elif sheet < local:
        return ('local_updated',local_server_date)
   

def get_log_status():
    pass

def update_local_facebook_profile_to_sheet(google_sheet_file_name,sheet_name,rows):
    gc = gspread.authorize(credentials)

    data = get_from_sheet("Campeign 001",sheet_name)
    existing_row = len(data)
    facebook_profile_gs = gc.open(google_sheet_file_name).worksheet(sheet_name)
    index = 1
    # data= facebook_profile_gs.get_all_records()
    # data= facebook_profile_gs.get_all_values()
    # facebook_profile_gs.clear()
    
    for row in rows:
        print(row[1])
        facebook_profile_gs.update_cell(existing_row + index,1,row[1])
        facebook_profile_gs.update_cell(existing_row + index,3,row[3])
        facebook_profile_gs.update_cell(existing_row + index,7,row[7])

        index += 1

    

    
    
    dataframe = pandas.DataFrame(facebook_profile_gs.get_all_records())
    df_copy = dataframe.copy()  
    # we'll work on a copy of the dataframe

    df_copy.drop_duplicates(subset=['profile_link'],keep='last',inplace=True)

    # print (len(df_copy))               
    # print (df_copy)   
    facebook_profile_gs.clear()            
    facebook_profile_gs.update([df_copy.columns.values.tolist()] + df_copy.values.tolist())


def add_log_to_sheet(google_sheet_file_name,sheet_name,date_time_latest=str(datetime.datetime.now())):
    gc = gspread.authorize(credentials)

    data = get_from_sheet("Campeign 001","logs")
    existing_row = len(data)
    fb_username_url_gs = gc.open(google_sheet_file_name).worksheet(sheet_name)
    fb_username_url_gs.update_cell(existing_row + 1,1,date_time_latest)
    fb_username_url_gs.update_cell(existing_row + 1,2,os.environ['COMPUTERNAME'])
    print("latest sheet log add successful")

# print(str(datetime.datetime.now()))
# update_log_to_sheet("Campeign 001","logs",str(datetime.datetime.now()))
# update_log_to_sheet("Campeign 001","logs",str(datetime.datetime.now()))
# update_log_to_sheet("Campeign 001","logs",str(datetime.datetime.now()))




class SQLite:
    
    DB_NAME = "miracle.db"
    local_user = os.environ['COMPUTERNAME'];
   
  
    def __init__(self):
        self.conn = self.create_connection()
  
    @classmethod
    def create_connection(cls):
        """
        create a database connection to the SQLite database specified by db_name
        :return: Connection object or None
        """
        conn = None
        try:
            
            # connects or creates a sqlite3 file
            conn = sqlite3.connect(cls.DB_NAME)
            return conn
        except Error as e:
            print(e)
              
        # returns the connection object
        return conn

    def get_local_latest_log(self):
        cursor = self.conn.cursor()
        latest_logs = cursor.execute("SELECT * FROM logs ORDER BY _pk_log DESC LIMIT 1")
        log_list= []
        local_log_last = "2021-01-04 01:47:00"
        for log in latest_logs:
            log_list.append(log)
        
        if len(log_list) > 0:
            local_log_last = log_list[0][1];

        # len_last = len(sheet_log_last.split(' ')[1].split(':')[0])
        # if len_last == 1:
        #     sheet_log_last = sheet_log_last[:11] + '0'+sheet_log_last.split(' ')[1].split(':')[0] + sheet_log_last[11 + 1:]
        #     # sheet_log_last[11] = '0'+sheet_log_last.split(' ')[1].split(':')[0]
        # print(sheet_log_last)
        # print(local_log_last)
        self.conn.commit()
        cursor.close()

        return local_log_last

    def check_latest_log_update_status(self):
        data = get_from_sheet("Campeign 001","logs")
        sheet_last_log_date = data[len(data)-1][0]
        local_last_log_date = self.get_local_latest_log()

        result = date_difference_status(sheet_last_log_date,local_last_log_date)

        return result

    def add_log_to_local(self,date=str(datetime.datetime.now())):
        cursor = self.conn.cursor()
        insert_table_sql = """INSERT INTO logs (last_update, local_user) 
        VALUES (?, ?);"""  
        cursor.execute(insert_table_sql, (date,self.local_user))
        self.conn.commit()
        print("latest log add successful")
        cursor.close()

    def remove_duplicate_data(self):
        c = self.conn.cursor()

        c.execute("""DELETE FROM facebook_profile
            WHERE _pk_facebook_profile NOT IN
            (
                SELECT MAX(_pk_facebook_profile) AS MaxRecordID
                FROM facebook_profile
                GROUP BY profile_link
            );""")
        self.conn.commit()

        c.close()
        
   
  
    def update_data_to_table(self, rows: list,log_date=str(datetime.datetime.now())):
        """Inserts the data from sheets to the table"""
          
        # initializing sql cursor
        c = self.conn.cursor()
          
        # excluding the first row because it 
        # contains the headers
        # insert_table_sql = """INSERT INTO details (timestamp, name, year) 
        # VALUES (?, ?, ?);"""
        # insert_table_sql = """INSERT INTO facebook_profile (profile_link, profile_id, last_update, _fk_profile_name, _fk_profile_gender,_fk_profile_country, _fk_profile_life_circle) VALUES (?, ?, ?, ?, ?, ?, ?);"""



        if(len(rows)>1):
            self.add_log_to_local(log_date)
            add_log_to_sheet("Campeign 001","logs",log_date)
            for row in rows[1:]:
                
                # inserts the data into the table
                # NOTE: the data needs to be in the order 
                # which the values are provided into the 
                # sql statement
                c.execute(
                    "INSERT INTO facebook_profile VALUES (:_pk_facebook_profile, :profile_link, :profile_id,:last_update,:_fk_profile_name,  :_fk_profile_gender,:_fk_profile_country, :_fk_profile_life_circle)",
                    {
                        '_pk_facebook_profile': None,
                        'profile_link': row[0],
                        'profile_id': None,
                        'last_update':str(log_date),
                        '_fk_profile_name': None,
                        '_fk_profile_country': None,
                        '_fk_profile_gender': None,
                        '_fk_profile_life_circle': row[6]
                    
                        
                    })

            # print(row)
            # c.execute(insert_table_sql, tuple(row))
              
        # committing all the changes to the database
        self.conn.commit()
          
        # closing the connection to the database
        c.close()

    def get_facebook_profile(self):
        cursor = self.conn.cursor()
        databaseLists = cursor.execute("SELECT * FROM facebook_profile")  
        data_list = []
        for data in databaseLists:
            data_list.append(data)
        cursor = self.conn.cursor()
        self.conn.commit()
        cursor.close()
        return data_list




if __name__ == '__main__':
    #      # fetches data from the sheets
    # data = get_from_sheet("Campeign 001","logs")  
    # sqlite_util = SQLite()
    #      # print(data[len(data)-1][0])
    # sqlite_util.check_latest_log_update(data[len(data)-1][0])
    #     # sqlite_util.update_log_to_local(datetime.datetime.now())

    sqlite_util_obj = SQLite()
    status,latest_date = sqlite_util_obj.check_latest_log_update_status()

    print(status,latest_date)

    data = get_from_sheet("Campeign 001","facebook_profile")
    # print(data)
    # sqlite_util_obj.add_data_to_table(data,latest_date)
    sqlite_util_obj.remove_duplicate_data()

    fb_profile_list = sqlite_util_obj.get_facebook_profile()

    update_local_facebook_profile_to_sheet("Campeign 001","facebook_profile",fb_profile_list)



    # data1 = "2021-09-04 01:47:00"
    # date2 = "2021-09-04 01:54:57.747115"
    # d1 = datetime.datetime.fromisoformat(data1)
    # d2 = datetime.datetime.fromisoformat(date2)
    # print(d1)
    # print(d2)
    # diff = d2 > d1
    # print(diff)