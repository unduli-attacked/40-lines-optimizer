import pandas as pd
import random
import requests
import time
import math
from datetime import datetime

class Downloader:
    lock = False # controls whether a new API request can be made
    user_endpoint = "https://ch.tetr.io/api/users/"
    summary_addl = "/summaries/40l"
    record_addl = "/records/40l/recent?limit=100"
    speed_limit = 1
    def __init__(self, leaderboard_file):
        self.leaderboard_df = pd.read_csv(leaderboard_file)
        self.session_id = "OPTIMIZER_"+str(random.randbytes(16).hex())
        self.headers = {'User-Agent':':P'}
        self.headers_sesh = {"X-Session-ID":self.session_id, 'User-Agent':':P'}

    def pull_demog_data(self, username):
        # lookup user endpoint
        endpoint = self.user_endpoint+username.strip()

        usrStart = time.time()

        try:
            user_info = requests.get(endpoint, headers=self.headers)
        except Exception as e:
            #FIXME actually handle this error
            print("Demog request failed for user", username, ". Error:", e)
            return -1
        print(user_info.json())
        if user_info.status_code == 200:
            # user info data retrieved
            try:
                user_info_data = user_info.json()["data"]
                demog_data = {
                    "id": user_info_data["_id"], 
                    "username": user_info_data.get("username", None),
                    "country": user_info_data.get("country", None), 
                    "created_date": user_info_data.get("ts", None), 
                    "xp": user_info_data.get("xp", math.nan), 
                    "achievement_rating": user_info_data.get("ar", math.nan), 
                    "TL_games_played": user_info_data.get("gamesplayed", math.nan), 
                    "TL_games_won": user_info_data.get("gameswon", math.nan), 
                    "TL_play_time": user_info_data.get("gametime", math.nan), 
                    "num_records": 0
                }
                # record end time
                usrEnd = time.time()        

                # determine if the speed limit has been met
                if self.speed_limit > (usrEnd - usrStart):
                    # speed limit has not been met, sleep for remaining time
                    time.sleep(self.speed_limit - (usrEnd - usrStart))
                print(demog_data)
                return demog_data
        
            except Exception as e:
                #FIXME actually handle this
                print("Failed to retrieve user", username,". Error:", e)
                return -1

    def pull_summ_data(self, username):
        endpoint = self.user_endpoint+username+self.summary_addl

        summStart = time.time()

        try:
            summ_info = requests.get(endpoint, headers=self.headers)
        except Exception as e:
            #FIXME actually handle this error
            print("Summary request failed for user", username, ". Error:", e)
            return -1

        if summ_info.status_code == 200:
            try:
                summ_info_data = summ_info.json()["data"]
                summ_data = {
                    "best_time": summ_info_data.get('record', {}).get('results', {}).get('stats', {}).get('finaltime', math.nan),
                    "best_record": summ_info_data.get('record', {}).get('_id', None),
                    "live_rank": summ_info_data.get('rank', -1), # note: this will be -1 if unranked
                    "prisecter": str(summ_info_data.get('p', {}).get('pri', 0)) + ':' + str(summ_info_data.get('p', {}).get('sec', 0)) + ':' + str(summ_info_data.get('p', {}).get('ter', 0))
                }
                # record end time
                summEnd = time.time()        

                # determine if the speed limit has been met
                if self.speed_limit > (summEnd - summStart):
                    # speed limit has not been met, sleep for remaining time
                    time.sleep(self.speed_limit - (summEnd - summStart))
                return summ_data
            except Exception as e:
                return -1
        

    def processRecord(record_json, username):
        try:
            results = record_json["results"]
            record_row = {
                "record_id": record_json["_id"], 
                "username": username, 
                "datetime": record_json.get("ts", None), 
                "current_pb": record_json.get("pb", False), 
                "once_pb": record_json.get("oncepb", False), 
                "final_time": results.get("stats", {}).get("finaltime", math.nan), 
                "pps": results.get("aggregatestats", {}).get("pps", math.nan), 
                "inputs": results.get("stats", {}).get("inputs", math.nan), 
                "score": results.get("stats", {}).get("score", math.nan), 
                "pieces_placed": results.get("stats", {}).get("piecesplaced", math.nan), 
                "singles": sum([results['stats']['clears']['singles'], results['stats']['clears']['minitspinsingles'], results['stats']['clears']['tspinsingles']]) if ('stats' in results) and ('clears' in results['stats']) else math.nan,
                "doubles": sum([results['stats']['clears']['doubles'], results['stats']['clears']['minitspindoubles'], results['stats']['clears']['tspindoubles']]) if ('stats' in results) and ('clears' in results['stats']) else math.nan, 
                "triples": sum([results['stats']['clears']['triples'], results['stats']['clears']['minitspintriples'], results['stats']['clears']['tspintriples']]) if ('stats' in results) and ('clears' in results['stats']) else math.nan, 
                "quads": sum([results['stats']['clears']['quads'], results['stats']['clears']['minitspinquads'], results['stats']['clears']['tspinquads']]) if ('stats' in results) and ('clears' in results['stats']) else math.nan, 
                "all_clears": results.get("stats", {}).get("clears", {}).get("allclear", math.nan), 
                "finesse_faults": results.get("stats", {}).get("finesse", {}).get("faults", math.nan), 
                "finesse_perf": results.get("stats", {}).get("finesse", {}).get("perfectpieces", math.nan)
            }
            # print(record_row)
            return record_row
        except Exception as e:
            print("Failed to retrieve record for", username,". Error:", e)
            return None

    def pull_game_data(self, username):
        records_df = pd.DataFrame()
        endpoint = self.user_endpoint+username+self.record_addl
        last_prisecter = ""
        while True:
            req_url = endpoint
            if last_prisecter != "":
                req_url += "&after="+last_prisecter
            
            pgStart = time.time()
            try:
                user_recent = requests.get(req_url, headers=self.headers_sesh)
            except Exception as e:
                print("Record request for user", username, "at prisecter", last_prisecter, "failed. Error:", e)
                continue
            

            if user_recent.status_code == 200:
                recent_data = user_recent.json()["data"]["entries"]
                if len(recent_data) < 1:
                    return records_df
                for rec in recent_data:
                    ret_rec = self.processRecord(rec, username)
                    if ret_rec:
                        records_df = pd.concat([records_df, pd.DataFrame(ret_rec, index=[0])], ignore_index=True)
                
                last_prisecter = str(rec["p"]["pri"])+":"+str(rec["p"]["sec"])+":"+str(rec["p"]["ter"])

            pgEnd = time.time()
            # determine if the speed limit has been met
            if self.speed_limit > (pgEnd - pgStart):
                # speed limit has not been met, sleep for remaining time
                time.sleep(self.speed_limit - (pgEnd - pgStart))
        return records_df

    def pull_user(self, username):
        demog_data = self.pull_demog_data(username)
        summ_data = self.pull_summ_data(username)

        user_data = demog_data | summ_data
        if user_data['created_date']:
            user_data['time_played'] = time.time() - datetime.fromisoformat(user_data['created_date']).timestamp()
        else:
            user_data['time_played'] = None

        # get records
        record_df = self.pull_game_data(username)
        record_df["kps"] = record_df["inputs"] / (record_df["final_time"] / 1000) # keys per second
        record_df["kpp"] = record_df["inputs"] / record_df["pieces_placed"] # keys per piece
        record_df["percent_perf"] = record_df["finesse_perf"] / record_df["pieces_placed"] # percent of pieces placed with perfect finesse

        # aggregate
        attrs_to_grab = ["final_time","pps","inputs","score","pieces_placed","singles","doubles","triples","quads","all_clears","finesse_faults","finesse_perf", "percent_perf", "kpp", "kps"]
        for attr in attrs_to_grab:
            user_data[attr+'_avg'] = record_df[attr].mean()
            user_data[attr+'_pb'] = record_df[attr].loc[record_df['current_pb'] == True]
        
        return user_data

class Analyzer:
    def __init__(self):
        pass

test = True
if test==True:
    dl = Downloader('data/leaderboard_2024.csv')
    demog = dl.pull_demog_data('badwolf5940')
    print(demog)