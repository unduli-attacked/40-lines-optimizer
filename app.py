from flask import Flask, render_template, request, url_for, redirect
import pandas as pd
from analysis_util import Downloader, Analyzer

app = Flask(__name__)

dl = Downloader('data/leaderboard_2024.csv')
an = Analyzer()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/results/<username>')
def results(username):
    user_info = dl.pull_user(username)
    cluster_info = an.analyze_user(user_info)
    return render_template("results.html", username=username, user_info=user_info, cluster_info=cluster_info)

@app.route('/search', methods=['POST'])
def search():
    # TODO add loading page
    username = request.form.get('username')
    print("Searching for",username)
    return redirect(url_for('results', username=username))



if __name__=="__main__":
    app.run(debug=True)