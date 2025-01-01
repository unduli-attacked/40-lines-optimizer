import pandas as pd
import random
import requests
import time
import math
from datetime import datetime
from threading import Lock
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np
import json

class Downloader:
    user_endpoint = "https://ch.tetr.io/api/users/"
    summary_addl = "/summaries/40l"
    record_addl = "/records/40l/recent?limit=100"
    speed_limit = 1
    def __init__(self, leaderboard_file):
        self.leaderboard_df = pd.read_csv(leaderboard_file)
        self.session_id = "OPTIMIZER_"+str(random.randbytes(16).hex())
        self.headers = {'User-Agent':':P'}
        self.headers_sesh = {"X-Session-ID":self.session_id, 'User-Agent':':P'}
        self.lock = Lock()

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
        # print(user_info.json())
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
                    "pri": summ_info_data.get('record', {}).get('p', {}).get('pri', 0),
                    "sec": summ_info_data.get('record', {}).get('p', {}).get('sec', 0),
                    "ter": summ_info_data.get('record', {}).get('p', {}).get('ter', 0)
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
        

    def processRecord(self, record_json, username):
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
    
    def place_rank(self, pri, sec, ter):
        before = self.leaderboard_df.loc[self.leaderboard_df['pri'] >= pri]
        if pri in before['pri'].values:
            # need sec
            before = before.loc[before['sec'] >= sec]
            if sec in before['sec'].values:
                before = before.loc[before['ter'] >= ter]
        rank = before['rank'].max() + 0.5
        del before
        return rank


    def pull_user(self, username):
        self.lock.acquire()
        demog_data = self.pull_demog_data(username)
        summ_data = self.pull_summ_data(username)
        # get records
        record_df = self.pull_game_data(username)
        self.lock.release()

        user_data = demog_data | summ_data
        if user_data['created_date']:
            user_data['time_played'] = time.time() - datetime.fromisoformat(user_data['created_date']).timestamp()
        else:
            user_data['time_played'] = None

        
        record_df["kps"] = record_df["inputs"] / (record_df["final_time"] / 1000) # keys per second
        record_df["kpp"] = record_df["inputs"] / record_df["pieces_placed"] # keys per piece
        record_df["percent_perf"] = record_df["finesse_perf"] / record_df["pieces_placed"] # percent of pieces placed with perfect finesse
        
        # aggregate
        attrs_to_grab = ["final_time","pps","inputs","score","pieces_placed","singles","doubles","triples","quads","all_clears","finesse_faults","finesse_perf", "percent_perf", "kpp", "kps"]
        for attr in attrs_to_grab:
            user_data[attr+'_avg'] = float(record_df[attr].mean())
            user_data[attr+'_pb'] = float(record_df[attr].loc[record_df['current_pb'] == True].values[0])
        user_data['rank'] = self.place_rank(user_data['pri'], user_data['sec'], user_data['ter'])
        return user_data

class Analyzer:
    feature_set = ['rank', 'kps_pb', 'final_time_pb', 'kps_avg', 'final_time_avg', 'pps_pb', 'pps_avg', 'achievement_rating', 'xp', 'all_clears_avg', 'all_clears_pb', 'TL_play_time', 'TL_games_played', 'TL_games_won', 'time_played', 'num_records', 'inputs_pb', 'kpp_pb', 'score_pb', 'score_avg', 'finesse_faults_pb', 'percent_perf_pb', 'doubles_avg', 'finesse_perf_pb', 'doubles_pb', 'kpp_avg', 'finesse_faults_avg', 'inputs_avg', 'pieces_placed_pb']
    improveable_attrs = {
        'num_records': "number of 40-lines games played", 
        'pps_pb': "number of pieces placed per second (PPS)",
        'inputs_pb': "number of inputs", 
        'score_pb': "score",  
        'percent_perf_pb': "percent of pieces placed with perfect finesse (finesse %)", 
        'kpp_pb': "number of keys pressed per piece (KPP)", 
        'kps_pb': "number of keys pressed per second (KPS)"
    }
    def __init__(self):
        self.best_df = pd.read_csv('data/best_in_cluster.csv', index_col=[0])
        self.median_df = pd.read_csv('data/median_in_cluster.csv', index_col=[0])
        self.means_df = pd.read_csv('data/cluster_means.csv')
        self.advice = json.load(open('data/advice_text.json', 'r'))
        cluster_centers = np.vstack(pd.read_csv('data/cluster_centers.csv'))
        self.model = KMeans(init=cluster_centers)
        self.scaler = StandardScaler()
    
    def get_cluster(self, user_info):
        feature_arr = []
        for key in self.feature_set:
            feature_arr.append(user_info[key])
        scaled_features = self.scaler.fit_transform(feature_arr) #FIXME scaler needs 2d, pull parmas from full dataset?
        return self.model.predict(scaled_features)
    
    def calc_attr_dist(self, user, bestUser, means):
        dists = {}
        for attr in self.improveable_attrs.keys():
            dist = (user[attr]) - (bestUser[attr])
            dist = dist / means[attr]
            dists[dist] = attr #math.sqrt((user[attr] - bestUser[attr])**2)
        return dists

    def get_improvables(self, user_info, best_user):

        dists = self.calc_attr_dist(user_info, best_user[self.improveable_attrs.keys()], self.means_df.loc[self.means_df['cluster'] == best_user['cluster']])
        min_dist = dists[min(dists.keys())]
        max_dist = dists[max(dists.keys())]
        closest_zero = dists[min(dists.keys(), key=lambda x: abs(x))]

        return min_dist, max_dist, closest_zero
    
    def analyze_user(self, user_info):
        cluster_info = {'username':user_info['username']}
        cluster_info['cluster'] = self.get_cluster(user_info)
        best_user = self.best_df.loc[self.best_df['cluster'] == cluster_info['cluster']]

        lower, higher, similar = self.get_improvables(user_info, best_user)

        cluster_info['lower_attr'] = self.improveable_attrs[lower]
        cluster_info['lower_good'] = self.advice[lower.strip('_pb')]['minimize']
        cluster_info['lower_text'] = self.advice[lower.strip('_pb')]['text']

        cluster_info['higher_attr'] = self.improveable_attrs[higher]
        cluster_info['higher_good'] = not self.advice[higher.strip('_pb')]['minimize']
        cluster_info['higher_text'] = self.advice[higher.strip('_pb')]['text']

        cluster_info['similar_attr'] = self.improveable_attrs[similar]

        cluster_info['top_user'] = best_user['username']
        cluster_info['top_rank'] = best_user['rank']

        cluster_info['median_rank'] = self.median_df.loc[self.median_df['cluster'] == cluster_info['cluster']]
        cluster_info['ab_average'] = 'above' if user_info['rank'] < cluster_info['median_rank'] else 'below'

        return cluster_info


test = False
if test==True:
    dl = Downloader('data/leaderboard_2024.csv')
    # user = dl.pull_user('badwolf5940')
    demog_data = dl.pull_demog_data('badwolf5940')
    summ_data = dl.pull_summ_data('badwolf5940')
    user_data = demog_data | summ_data
    user_data['rank'] = dl.place_rank(user_data['pri'], user_data['sec'], user_data['ter'])
    print(user_data)