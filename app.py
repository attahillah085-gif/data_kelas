from flask import Flask, request, render_template, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "admin" and password == "admin":
            return redirect("/dashboard")
        else:
            return "Login gagal!"
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/kas", methods=["GET", "POST"])
def kas():
    if request.method == "POST":
        nama = request.form["nama"]
        jumlah = int(request.form["jumlah"])
        tanggal = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect("kas.db")
        c = conn.cursor()
        c.execute("INSERT INTO kas (nama, jumlah, tanggal) VALUES (?, ?, ?)", (nama, jumlah, tanggal))
        conn.commit()
        conn.close()
        return redirect("/kas")
    
    conn = sqlite3.connect("kas.db")
    c = conn.cursor()
    c.execute("SELECT * FROM kas")
    data_kas = c.fetchall()
    conn.close()
    return render_template("kas.html", data=data_kas)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)