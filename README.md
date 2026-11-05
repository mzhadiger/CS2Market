# CS2 Skin Marketplace

I made this as my final project for CSCI 300 (Database Management) in Spring 2026, and now it's public so anyone can look through it or run it. It's a small website where you can buy, sell and rent Counter-Strike 2 skins with fake money. The skin catalog is real and comes from the [CSGO-API](https://github.com/ByMykel/CSGO-API). The users, listings, sales and prices are made up.

The main idea is renting. Instead of paying full price for an expensive skin, you can rent it for a few days and pay a deposit. When the rental time is over, MySQL gives the skin back to the owner on its own.

It's built with Flask and MySQL. I didn't use an ORM because the point of the class was to write the SQL myself, so all the queries are in plain SQL.

## What you can do

* Browse and search listings by rarity, weapon type, price, and sale or rental
* Open a skin to see its price chart for the last 30 days
* Buy a skin (the site takes a 5% fee from the seller)
* Rent a skin for a number of days and return it early if you want your deposit back
* See your inventory and how much it's worth
* See the skins you're renting and the ones other people are renting from you

New accounts get $500 to play with.

## What you need

* Python 3.10 or newer
* MySQL 8.0 or newer

## How to run it

**1. Get the code and install the packages**

```
git clone <this repo's link>
cd cs2_marketplace
python -m venv .venv
```

Turn on the virtual environment.

Windows:
```
.venv\Scripts\activate
```

Mac or Linux:
```
source .venv/bin/activate
```

Then install the packages:
```
pip install -r requirements.txt
```

**2. Make your .env file**

Copy `.env.example` and name the copy `.env`. Open it and put in your MySQL password. Your username too, if it isn't root.

**3. Set up the database**

Run these four files in this order. The order matters.

```
mysql -u root -p < schema.sql
mysql -u root -p < seed_data.sql
mysql -u root -p < views_update.sql
mysql -u root -p < refresh_dates.sql
```

If you use MySQL Workbench, you can open each file and run it there instead.

`schema.sql` makes the database, tables, views and the event that ends rentals. `seed_data.sql` fills it with data. `views_update.sql` updates one of the views, and the site won't work right without it. `refresh_dates.sql` moves all the dates in the data up to today. Without it the price chart would be empty, because the data was made back in April 2026.

**4. Set the demo passwords**

```
python setup_demo_users.py
```

**5. Start the site**

```
python app.py
```

Then go to http://127.0.0.1:5000

## Demo accounts

All of these use the password `demo1234`.

| Username | What it's good for |
|---|---|
| s1mple_fan_99 | buying |
| ZywOo_GOAT | selling |
| device_CPH | trading |
| NiKo_G2 | renting |

You can also just register a new account.

## The database

There are 8 tables:

* **Users** for accounts and wallet money
* **Weapons** like AK-47, AWP or Karambit
* **Skins**, the catalog of skins for each weapon
* **Inventory**, one row for each skin a user owns, with its own float and pattern
* **Listings** for skins that are up for sale or for rent
* **Transactions** for finished sales
* **Rentals** for who is renting what, and until when
* **PriceHistory** for daily prices used in the chart

There are also 5 views that the pages read from, plus an event called `ev_auto_return_rentals`. It runs every hour, ends rentals that are past their end date and puts those listings back up.

Buying, renting and returning each change several tables at once, so they run inside a transaction. If one step fails, nothing gets saved.

`queries.sql` has 7 example queries you can run to see what the data looks like.

## Making new seed data

You don't need to do this, since `seed_data.sql` is already in the repo. But if you want fresh data:

```
python seed_skins.py
```

It downloads the skin list (so it needs internet the first time) and writes a new `seed_data.sql`. Note that the prices will be different every time you run it.

## Things to know

* If the price chart is empty, run `refresh_dates.sql` again. The chart only shows the last 30 days, so it slowly runs out of data if you keep the database for a long time.
* The event scheduler has to be on for rentals to end by themselves. `schema.sql` turns it on, but if your MySQL user isn't allowed to do that, run `SET GLOBAL event_scheduler = ON;` as root.
* Rentals that are late still show up as overdue on the site even before the event runs.

## Files

```
app.py               all the pages and actions
auth.py              login, register and logout
db.py                small helpers for running queries
config.py            reads settings from .env
schema.sql           tables, views and the rental event
views_update.sql     updated version of v_active_listings
seed_data.sql        the data
refresh_dates.sql    moves the data's dates up to today
seed_skins.py        script that made seed_data.sql
setup_demo_users.py  sets the demo passwords
queries.sql          example queries
templates/           HTML pages
static/              CSS and JavaScript
```

## Credits

Skin names and images are from [ByMykel/CSGO-API](https://github.com/ByMykel/CSGO-API). This is a student project and has nothing to do with Valve. No real money or real skins are involved.
