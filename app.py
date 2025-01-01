from flask import Flask, render_template, request, url_for, redirect
import pandas as pd
from analysis_util import Downloader

app = Flask(__name__)

dl = Downloader('data/leaderboard_2024.csv')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/results/<username>')
def results(username):
    return render_template("results.html", username=username, user_info=dl.pull_user(username))

@app.route('/search', methods=['POST'])
def search():
    print(request.args)
    username = request.form.get('username')
    print(username)
    return redirect(url_for('results', username=username))



if __name__=="__main__":
    app.run(debug=True)