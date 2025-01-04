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
from joblib import load
from io import BytesIO
import matplotlib.pyplot as plt
import base64

class Downloader:
    user_endpoint = "https://ch.tetr.io/api/users/"
    summary_addl = "/summaries/40l"
    record_addl = "/records/40l/recent?limit=100"
    speed_limit = 1
    def __init__(self, leaderboard_file, debug=False):
        self.leaderboard_df = pd.read_csv(leaderboard_file)
        self.session_id = "OPTIMIZER_"+str(random.randbytes(16).hex())
        self.headers = {'User-Agent':':P'}
        self.headers_sesh = {"X-Session-ID":self.session_id, 'User-Agent':':P'}
        self.lock = Lock()
        self.debug = debug

    def pull_demog_data(self, username):
        # lookup user endpoint
        endpoint = self.user_endpoint+username.strip()

        usrStart = time.time()

        try:
            user_info = requests.get(endpoint, headers=self.headers)
        except Exception as e:
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
                if self.debug: print(demog_data)
                return demog_data
        
            except Exception as e:
                print("Failed to retrieve user", username,". Error:", e)
                return -1
        else:
            print("Demog request failed for user", username, ". Error:", user_info.json().get('error').get('msg'))
            return -1

    def pull_summ_data(self, username):
        endpoint = self.user_endpoint+username+self.summary_addl

        summStart = time.time()

        try:
            summ_info = requests.get(endpoint, headers=self.headers)
        except Exception as e:
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
        else:
            print("Summary request failed for user", username, ". Error:", summ_info.json().get('error', {}).get('msg', ''))
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
            else:
                print("Record request for user", username, "at prisecter", last_prisecter, "failed. Error:", user_recent.json().get('error', {}).get('msg', ''))
                continue
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
                # need ter
                before = before.loc[before['ter'] >= ter]
        rank = before['rank'].max() + 0.5
        del before
        return rank


    def pull_user(self, username):
        self.lock.acquire() # lock to prevent overrequesting
        demog_data = self.pull_demog_data(username)
        if demog_data == -1: return -1 # user not found
        summ_data = self.pull_summ_data(username)
        if summ_data == -1: return -1 # user not found
        # get records
        record_df = self.pull_game_data(username)
        self.lock.release() # unlock
        if len(record_df.dropna()) < 1: return -1 # no records found

        user_data = demog_data | summ_data
        if user_data['created_date']:
            user_data['time_played'] = time.time() - datetime.fromisoformat(user_data['created_date']).timestamp()
        else:
            user_data['time_played'] = None
        user_data['num_records'] = len(record_df)

        
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
    
    def __init__(self, debug=False):
        self.best_df = pd.read_csv('data/best_in_cluster.csv', index_col=[0])
        self.avgs_df = pd.read_csv('data/cluster_avgs.csv', index_col=[0])
        self.stds_df = pd.read_csv('data/cluster_stds.csv', index_col=[0])
        self.advice = json.load(open('data/advice_text.json', 'r'))
        self.model = load('data/cluster_model.joblib')
        self.scaler = StandardScaler()
        self.debug = debug
    
    def cluster_scale(self, x):
        u = 2706116.195379935 # original sample set mean
        s = 15783157.09064165 # original sample set standard deviation

        return (x-u)/s
    
    
    def get_cluster(self, user_info):
        feature_arr = []
        for key in self.feature_set:
            feature_arr.append(self.cluster_scale(user_info[key]))
        return self.model.predict([feature_arr])[0]
    
    
    
    def get_advice(self, user, bestUser, means, stds):
        def attr_scale(label, value):
            return (value - means[label].values[0]) / stds[label].values[0]
        attr_advice = {}
        plt.rcParams.update({'font.size': 22})
        for attr_l in self.improveable_attrs.keys():
            name = self.improveable_attrs[attr_l]
            distBest = attr_scale(attr_l, user[attr_l]) - attr_scale(attr_l, bestUser[attr_l].values[0])
            distMean = attr_scale(attr_l, user[attr_l]) - 0 # the scaled mean will always be 0
            attr = attr_l if attr_l=='num_records' else attr_l[:-3]
            attr_advice[attr] = {}
            attr_advice[attr]['name'] = name
            best = 'better than' if (distBest < 0) == (self.advice[attr]['minimize']==True) else ('the same as' if distBest == 0 else 'worse than')
            mean = 'better than' if (distMean < 0) == (self.advice[attr]['minimize']==True) else ('' if distMean == 0 else 'worse than')
            
            if (not best.startswith('worse')) and (not mean.startswith('worse')):
                attr_advice[attr]['text'] = "Your {} is <strong>{} average</strong> for your cluster <i>and</i> {} {}'s. Congratulations!".format(name, mean, best, bestUser['username'].values[0])
            else:
                if not mean.startswith('worse'):
                    attr_advice[attr]['text'] = "Your {} is <strong>{} average</strong> for your cluster, but worse than {}'s.".format(name, mean, bestUser['username'].values[0])
                else:
                    attr_advice[attr]['text'] = "Your {} is <strong>worse than average</strong> for your cluster.".format(name)
                attr_advice[attr]['text'] += " This means you should work on <strong>{}</strong> your {}.</p><p>To do so, we'd recommend {}".format(('decreasing' if self.advice[attr]['minimize'] else 'increasing'), name, self.advice[attr]['text'])

            plt.figure(figsize=(10,10))
            plt.bar(['You', 'Average', bestUser['username'].values[0]], [user[attr_l], means[attr_l].values[0], bestUser[attr_l].values[0]])
            plt.xlabel('')
            plt.ylabel(" ".join(w.capitalize() for w in name.split()))
            chart = BytesIO()
            plt.savefig(chart, format='png')
            chart.seek(0)
            attr_advice[attr]['chart'] = base64.b64encode(chart.getvalue()).decode()

        return attr_advice
    
    # TODO add the improvenator
    def analyze_user(self, user_info):
        cluster_info = {'username':user_info['username']}
        cluster_info['cluster'] = self.get_cluster(user_info)
        # print(cluster_info['cluster'])
        best_user = self.best_df.loc[self.best_df['cluster'] == cluster_info['cluster']]

        cluster_info['attr_advice'] = self.get_advice(user_info, best_user, self.avgs_df.loc[self.avgs_df['cluster'] == cluster_info['cluster']], self.stds_df.loc[self.stds_df['cluster'] == cluster_info['cluster']])

        cluster_info['top_user'] = best_user['username'].values[0]
        cluster_info['top_rank'] = best_user['rank'].values[0]
        cluster_info['cluster_name'] = best_user['cluster_name'].values[0]

        cluster_info['mean_rank'] = round(self.avgs_df.loc[self.avgs_df['cluster'] == cluster_info['cluster']]['rank'].values[0])
        cluster_info['ab_average'] = 'above' if user_info['rank'] < cluster_info['mean_rank'] else 'below'

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