import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id = :user_id",
                          user_id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id",
                          user_id=session["user_id"])[0]['cash']

    # pass a list of lists to the template page, template is going to iterate it to extract the data into a table
    total = cash
    stocks = []
    for index, row in enumerate(rows):
        stock_info = lookup(row['symbol'])

        # create a list with all the info about the stock and append it to a list of every stock owned by the user
        stocks.append(list((stock_info['symbol'], stock_info['name'], row['shares'], stock_info['price'], round(stock_info['price'] * row['shares'], 2))))
        total += stocks[index][4]

    return render_template("index.html", stocks=stocks, cash=round(cash, 2), total=round(total, 2))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        shares=int(request.form.get("shares"))
        symbol=lookup(request.form.get("symbol"))['symbol']

        # Check if the stock symbol is valid
        if not lookup(symbol):
            return apology("Invalid stock", 403)

        # Calculate total value of the transaction
        price=lookup(symbol)['price']
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id",
        user_id=session["user_id"])[0]['cash']
        cash_after = cash - (price * float(shares))

        # If your account doesnot have enough money
        if cash_after < 0:
            return apology("Not enough money", 403)

        # If user already has one or more stocks from the same company
        stock = db.execute("SELECT shares FROM quotes WHERE user_id = :user_id AND symbol = :symbol",
        user_id=session["user_id"], symbol=symbol)

        # Insert into the stock table
        if not stock:
            db.execute("INSERT INTO quotes(user_id, symbol, shares) VALUES (:user_id, :symbol, :shares)",
            user_id=session["user_id"], symbol=symbol, shares=shares)

        # Update the stock table
        else:
            shares += stock[0]['shares']

            db.execute("UPDATE quotes SET shares = :shares WHERE user_id = :user_id AND symbol = :symbol",
                user_id=session["user_id"], symbol=symbol, shares=shares)

        # Update user's cash
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id",
                          cash=cash_after, user_id=session["user_id"])

        # Update history table
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price_per_share) VALUES (:user_id, :symbol, :shares, :price)",
        user_id=session["user_id"], symbol=symbol, shares=shares, price=price)

        # Redirect user to index page with a success message
        flash("Bought!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id = :user_id",
                            user_id=session["user_id"])
    # Create a list
    transactions = []
    for row in rows:
        stock_info = lookup(row['symbol'])

        # Write into that list all of the information
        transactions.append(list((stock_info['symbol'], stock_info['name'], row['shares'], row['price_per_share'], row['date'])))

    # redirect user to index page
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method =="POST":
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("invalid stock", 400)
        return render_template("quote.html", stock=stock)
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html", stock="")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure confirm password is correct
        elif request.form.get("password") != request.form.get("confirm-pass"):
           return apology("confirmation password does not match", 403)

        # Query database for username if exists
        elif db.execute("SELECT * FROM users WHERE username = :username",
            username=request.form.get("username")):
            return apology("username already taken", 403)

        # Insert new user and hash of the password into the table
        db.execute("INSERT INTO users(username, hash) VALUES (:username, :hash)",
        username = request.form.get("username"),
        hash=generate_password_hash(request.form.get("password")))

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        flash("Registered!")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        shares=int(request.form.get("shares"))
        symbol=request.form.get("symbol")
        price=lookup(symbol)["price"]
        value=round(price*float(shares))

        share_before = db.execute("SELECT shares FROM quotes WHERE user_id = :user_id AND symbol = :symbol",
        symbol=symbol, user_id=session["user_id"])[0]['shares']

        share_after = share_before - shares
        # If user sold all stocks of the same copany, then delete them.
        if share_after == 0:
            db.execute("DELETE FROM quotes WHERE user_id = :user_id AND symbol = :symbol",
                          symbol=symbol, user_id=session["user_id"])

        # If the user does not have enough stock
        elif share_after < 0:
            return apology("That's more than the stocks you owned", 403)
        # Update the table
        else:
            db.execute("UPDATE quotes SET shares = :shares WHERE user_id = :user_id AND symbol = :symbol",
            symbol=symbol, user_id=session["user_id"], shares=share_after)

        cash = db.execute("SELECT cash FROM users WHERE id = :user_id",
        user_id=session["user_id"])[0]['cash']

        cash_after = cash + price * float(shares)
        # Update the user's cash after selling stocks
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id",
        cash=cash_after, user_id=session["user_id"])
        # Insert new values into transactions table
        db.execute("INSERT INTO transactions(user_id, symbol, shares, price_per_share) VALUES (:user_id, :symbol, :shares, :price)",
        user_id=session["user_id"], symbol=symbol, shares=-shares, price=price)

        flash("Sold!")
        return redirect("/")
    else:
        # Query database with quotes table
        rows = db.execute("SELECT symbol, shares FROM quotes WHERE user_id = :user_id",
        user_id=session["user_id"])

        # Create a dictionary with the stocks after updating
        stocks = {}
        for row in rows:
            stocks[row['symbol']] = row['shares']

        return render_template("sell.html", stocks=stocks)

@app.route("/add_money", methods=["GET", "POST"])
@login_required
def add_money():

    if request.method == "POST":
            amount = float(request.form.get("amount"))
            if amount < 0:
                return apology("Amount must be a real number", 400)
            db.execute("UPDATE users SET cash = cash + :amount WHERE id = :user_id", user_id=session["user_id"], amount=amount)
            return redirect("/")
    else:
        return render_template("add_money.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)