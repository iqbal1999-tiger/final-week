import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session["user_id"]
    cash = db.execute("SELECT cash FROM users WHERE id = ?", id)
    balance = cash[0]["cash"]
    balance = round(balance, 3)
    accounts = db.execute("SELECT * FROM accounts WHERE account_id = ? AND number_of_shares >= 1 ", id)
    return render_template("index.html", accounts=accounts, balance=balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        id = session["user_id"]

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        shares = request.form.get("shares")
        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("invalid shares", 400)
        shares = int(shares)

        quotes = lookup(symbol)
        if quotes is None:
            return apology("invalid symbol", 400)

        cash = db.execute("SELECT cash FROM users WHERE id = ? ", id)
        cash = cash[0]["cash"]
        number_of_shares = db.execute(
            "SELECT number_of_shares FROM accounts JOIN users ON users.id = accounts.account_id WHERE users.id = ? AND symbol = ? ",
            id, quotes["symbol"]
        )
        cost = round(quotes["price"], 3) * float(shares)

        if float(cash) < cost:
            return apology("Can't Afford It ", 400)
        else:
            if number_of_shares == []:
                shares_balance = shares
                db.execute(
                    "INSERT INTO accounts (account_id,number_of_shares, price, symbol, name) VALUES (?,?,?,?,?)",
                    id, shares_balance, round(quotes["price"], 3), quotes["symbol"], quotes["name"]
                )
            else:
                shares_balance = int(number_of_shares[0]["number_of_shares"]) + shares

            balance = float(cash) - cost
            name_of_company = quotes["name"]
            db.execute("UPDATE users SET cash = ? WHERE id = ? ", balance, id)
            db.execute(
                "UPDATE accounts SET number_of_shares = ? WHERE account_id = ? AND  symbol = ? ",
                shares_balance, id, quotes["symbol"]
            )
            db.execute("UPDATE accounts SET price = ? WHERE symbol = ?", round(quotes["price"], 3), quotes["symbol"])
            db.execute(
                "INSERT INTO transactions (name_of_company,price ,symbol ,shares, type, user_id, transacted)  VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                name_of_company, round(quotes["price"], 3), quotes["symbol"], shares, "BUY", id
            )
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session["user_id"]
    accounts = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY transacted DESC", id)
    return render_template("history.html", accounts=accounts)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        quotes = lookup(symbol)
        if quotes is None:
            return apology("invalid symbol", 400)

        db.execute("UPDATE accounts SET price = ? WHERE symbol = ?", round(quotes["price"], 3), quotes["symbol"])
        return render_template("quoted.html", quotes=quotes)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        password1 = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        elif not password or not password1:
            return apology("must provide password", 400)
        elif password != password1:
            return apology("password doesn't match", 400)
        else:
            hash = generate_password_hash(password)
            try:
                new_id = db.execute("INSERT INTO users (username, hash ) VALUES (?,?)", username, hash)
                session["user_id"] = new_id
                return redirect("/")
            except ValueError:
                return apology("username already exists", 400)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    id = session["user_id"]
    accounts = db.execute("SELECT * FROM accounts WHERE account_id = ? AND number_of_shares >= 1 ", id)
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("missing symbol", 400)

        shares = request.form.get("shares")
        if not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("invalid shares", 400)
        shares = int(shares)

        cash = db.execute("SELECT cash FROM users WHERE id = ? ", id)
        cash = cash[0]["cash"]
        quotes = lookup(symbol)
        if quotes is None:
            return apology("invalid symbol", 400)

        number_of_shares = db.execute(
            "SELECT number_of_shares FROM accounts JOIN users ON users.id = accounts.account_id WHERE users.id = ? AND symbol = ? ",
            id, quotes["symbol"]
        )
        if number_of_shares == []:
            return apology("Missing symbol", 400)

        cost = round(quotes["price"], 3) * shares
        if int(number_of_shares[0]["number_of_shares"]) < shares:
            return apology("You don't know enough shares", 400)
        else:
            present_shares = int(number_of_shares[0]["number_of_shares"]) - shares
            present_balance = float(cash) + cost
            name_of_company = quotes["name"]
            db.execute("UPDATE users SET cash = ? WHERE id = ? ", present_balance, id)
            db.execute(
                "UPDATE accounts SET number_of_shares = ? WHERE account_id = ? AND  symbol = ? ",
                present_shares, id, quotes["symbol"]
            )
            db.execute("UPDATE accounts SET price = ? WHERE symbol = ?", round(quotes["price"], 3), quotes["symbol"])
            db.execute(
                "INSERT INTO transactions (name_of_company,price ,symbol ,shares, type, user_id, transacted)  VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                name_of_company, round(quotes["price"], 3), quotes["symbol"], shares, "SELL", id
            )
            return redirect("/")
    else:
        return render_template("sell.html", accounts=accounts)
