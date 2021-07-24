# Get Data from Google Sheet
import sqlite3

import gspread
from google.oauth2.service_account import Credentials

scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

credentials = Credentials.from_service_account_file(
    'Spreed_Sheet_Data.json',
    scopes=scopes
)

gc = gspread.authorize(credentials)
fb_username_url_gs = gc.open("Campeign 001").worksheet('InternationPeople')
list_of_fb_profile = fb_username_url_gs.get_all_values()


for list in list_of_fb_profile:
    profile_info = list
    for profile_link in profile_info:
        facebook_username_url = profile_info[0]
        # TODO: Misleading Data Direction Data Should Go to _fk_profile_country but Its Go to _fk_profile_gender
        facebook_user_country = profile_info[1]

        # Insert Data to Database
        connection = sqlite3.connect('../DatabaseCreation/wws.db')
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO facebook_profile VALUES (:_pk_facebook_profile, :profile_link, :_fk_profile_name, :_fk_profile_country, :_fk_profile_gender, :_fk_profile_life_circle)",
            {
                '_pk_facebook_profile': None,
                'profile_link': facebook_username_url,
                '_fk_profile_country': facebook_user_country,
                '_fk_profile_name': None,
                '_fk_profile_gender': None,
                '_fk_profile_life_circle': None

            })

        connection.commit()
        connection.close()
        break

print("Get Data from Google Sheet successfully")

