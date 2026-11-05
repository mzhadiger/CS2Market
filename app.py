# Main Flask app for the CS2 skin marketplace. Login, register and logout are in auth.py.
from datetime import date, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash, abort, jsonify,
)
from flask_login import login_required, current_user

import db
from config import Config
from auth import auth_bp, login_manager

app = Flask(__name__)
app.config.from_object(Config)

db.init_pool(app)
login_manager.init_app(app)
app.register_blueprint(auth_bp)


# I put these here so every template gets the filter lists for the sidebar.
# Otherwise I would have to pass them in from every route.
@app.context_processor
def inject_filters():
    rarities = [
        "Consumer", "Industrial", "Mil-Spec", "Restricted",
        "Classified", "Covert", "Contraband", "Exceedingly Rare",
    ]
    weapon_types = ["rifle", "pistol", "smg", "shotgun",
                    "sniper", "knife", "gloves", "machinegun"]
    return {
        "all_rarities": rarities,
        "all_weapon_types": weapon_types,
    }


@app.route("/")
def home():
    featured = db.query_one(
        "SELECT s.skin_id, s.name AS skin_name, s.rarity, s.collection, "
        "       s.base_price, s.image_url, w.name AS weapon_name "
        "  FROM Skins s JOIN Weapons w ON s.weapon_id = w.weapon_id "
        " WHERE s.image_url IS NOT NULL "
        " ORDER BY s.base_price DESC LIMIT 1"
    )
    trending = db.query_all(
        "SELECT s.skin_id, s.name AS skin_name, s.rarity, s.image_url, "
        "       w.name AS weapon_name, COUNT(l.listing_id) AS listing_count "
        "  FROM Skins s "
        "  JOIN Weapons   w ON s.weapon_id    = w.weapon_id "
        "  JOIN Inventory i ON i.skin_id      = s.skin_id "
        "  JOIN Listings  l ON l.inventory_id = i.inventory_id "
        " WHERE l.status = 'active' "
        " GROUP BY s.skin_id "
        " ORDER BY listing_count DESC, s.base_price DESC "
        " LIMIT 4"
    )
    rarity_counts = db.query_all(
        "SELECT rarity, COUNT(*) AS count FROM Skins "
        " GROUP BY rarity ORDER BY FIELD(rarity,'Contraband','Covert',"
        "'Classified','Restricted','Mil-Spec','Industrial','Consumer',"
        "'Exceedingly Rare')"
    )
    listings = db.query_all(
        "SELECT * FROM v_active_listings ORDER BY created_at DESC LIMIT 12"
    )
    stats = db.query_one("SELECT * FROM v_marketplace_stats")
    return render_template("index.html",
                           featured=featured, trending=trending,
                           rarity_counts=rarity_counts,
                           listings=listings, stats=stats)


@app.route("/search")
def search():
    # Only add a condition when the user actually picked that filter.
    # The values still go through %s so this is safe from SQL injection.
    where, params = ["1 = 1"], []

    if r := request.args.get("rarity"):
        where.append("rarity = %s")
        params.append(r)
    if wt := request.args.get("weapon_type"):
        where.append("weapon_type = %s")
        params.append(wt)
    if lt := request.args.get("listing_type"):
        where.append("listing_type = %s")
        params.append(lt)
    if (mn := request.args.get("min_price", type=float)) is not None:
        where.append("COALESCE(sale_price, daily_rental_rate) >= %s")
        params.append(mn)
    if (mx := request.args.get("max_price", type=float)) is not None:
        where.append("COALESCE(sale_price, daily_rental_rate) <= %s")
        params.append(mx)
    if q := request.args.get("q"):
        where.append("(skin_name LIKE %s OR weapon_name LIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    # order_by only comes from this dict and never straight from the URL,
    # so it is fine to put it in the f-string below.
    sort = request.args.get("sort", "newest")
    order_by = {
        "price_asc":  "COALESCE(sale_price, daily_rental_rate) ASC",
        "price_desc": "COALESCE(sale_price, daily_rental_rate) DESC",
        "newest":     "created_at DESC",
        "rarity":     "FIELD(rarity,'Contraband','Covert','Classified',"
                      "'Restricted','Mil-Spec','Industrial','Consumer',"
                      "'Exceedingly Rare') ASC",
    }.get(sort, "created_at DESC")

    sql = (
        f"SELECT * FROM v_active_listings "
        f" WHERE {' AND '.join(where)} "
        f" ORDER BY {order_by} LIMIT 100"
    )
    listings = db.query_all(sql, tuple(params))
    return render_template("search.html", listings=listings, args=request.args)


@app.route("/skin/<int:skin_id>")
def skin_detail(skin_id):
    skin = db.query_one(
        "SELECT s.skin_id, s.name AS skin_name, s.rarity, s.collection, "
        "       s.base_price, s.image_url, s.has_stattrak, s.has_souvenir, "
        "       w.weapon_id, w.name AS weapon_name, w.weapon_type "
        "  FROM Skins s JOIN Weapons w ON s.weapon_id = w.weapon_id "
        " WHERE s.skin_id = %s",
        (skin_id,),
    )
    if not skin:
        abort(404)

    active_listings = db.query_all(
        "SELECT * FROM v_active_listings WHERE skin_id = %s "
        "ORDER BY COALESCE(sale_price, daily_rental_rate) ASC",
        (skin_id,),
    )
    price_history = db.query_all(
        "SELECT recorded_date, wear_category, avg_price, sales_volume "
        "  FROM v_price_trends_30d WHERE skin_id = %s "
        " ORDER BY recorded_date",
        (skin_id,),
    )
    related = db.query_all(
        "SELECT s.skin_id, s.name AS skin_name, s.rarity, s.image_url, "
        "       w.name AS weapon_name, s.base_price "
        "  FROM Skins s JOIN Weapons w ON s.weapon_id = w.weapon_id "
        " WHERE s.weapon_id = %s AND s.skin_id <> %s "
        "   AND s.image_url IS NOT NULL "
        " ORDER BY s.base_price DESC LIMIT 4",
        (skin["weapon_id"], skin_id),
    )
    return render_template("skin_detail.html",
                           skin=skin, listings=active_listings,
                           price_history=price_history, related=related)


@app.route("/listing/<int:listing_id>")
def listing_detail(listing_id):
    row = db.query_one(
        "SELECT l.*, "
        "       s.skin_id, s.name AS skin_name, s.rarity, s.image_url, "
        "       w.name AS weapon_name, w.weapon_type, "
        "       i.wear_category, i.float_value, i.is_stattrak, i.paint_seed, "
        "       u.username AS seller_username, u.reputation AS seller_reputation "
        "  FROM Listings l "
        "  JOIN Inventory i ON l.inventory_id = i.inventory_id "
        "  JOIN Skins     s ON i.skin_id      = s.skin_id "
        "  JOIN Weapons   w ON s.weapon_id    = w.weapon_id "
        "  JOIN Users     u ON l.seller_id    = u.user_id "
        " WHERE l.listing_id = %s",
        (listing_id,),
    )
    if not row:
        abort(404)
    return render_template("listing_detail.html", listing=row)


@app.route("/inventory")
@login_required
def my_inventory():
    items = db.query_all(
        "SELECT * FROM v_user_inventory WHERE user_id = %s "
        "ORDER BY estimated_value DESC",
        (current_user.id,),
    )
    summary = db.query_one(
        "SELECT COUNT(*) AS item_count, "
        "       COALESCE(SUM(s.base_price), 0) AS total_value, "
        "       COUNT(DISTINCT s.rarity) AS rarity_variety "
        "  FROM Inventory i JOIN Skins s ON i.skin_id = s.skin_id "
        " WHERE i.user_id = %s",
        (current_user.id,),
    )
    rarity_dist = db.query_all(
        "SELECT s.rarity, COUNT(*) AS count "
        "  FROM Inventory i JOIN Skins s ON i.skin_id = s.skin_id "
        " WHERE i.user_id = %s "
        " GROUP BY s.rarity "
        " ORDER BY FIELD(s.rarity,'Contraband','Covert','Classified',"
        "'Restricted','Mil-Spec','Industrial','Consumer','Exceedingly Rare')",
        (current_user.id,),
    )
    return render_template("inventory.html",
                           items=items, summary=summary,
                           rarity_dist=rarity_dist)


@app.route("/rentals")
@login_required
def my_rentals():
    renting = db.query_all(
        "SELECT r.* FROM v_rental_status r "
        "  JOIN Rentals base ON base.rental_id = r.rental_id "
        " WHERE base.renter_id = %s "
        " ORDER BY FIELD(r.effective_status,'overdue','active','returned','cancelled'),"
        "          r.end_date ASC",
        (current_user.id,),
    )
    leasing_out = db.query_all(
        "SELECT r.* FROM v_rental_status r "
        "  JOIN Rentals base ON base.rental_id = r.rental_id "
        " WHERE base.owner_id = %s "
        " ORDER BY FIELD(r.effective_status,'overdue','active','returned','cancelled'),"
        "          r.end_date ASC",
        (current_user.id,),
    )
    earnings = db.query_one(
        "SELECT COALESCE(SUM(total_cost), 0) AS lifetime_earnings, "
        "       COUNT(*) AS total_rentals "
        "  FROM Rentals WHERE owner_id = %s AND status IN ('active','returned')",
        (current_user.id,),
    )
    return render_template("rentals.html",
                           renting=renting, leasing_out=leasing_out,
                           earnings=earnings)


@app.route("/listing/<int:listing_id>/buy", methods=["POST"])
@login_required
def buy_listing(listing_id):
    listing = db.query_one(
        "SELECT l.*, i.user_id AS current_owner_id "
        "  FROM Listings l JOIN Inventory i ON l.inventory_id = i.inventory_id "
        " WHERE l.listing_id = %s",
        (listing_id,),
    )
    if not listing or listing["status"] != "active" or listing["listing_type"] != "sale":
        flash("That listing is no longer available.", "error")
        return redirect(url_for("home"))
    if listing["seller_id"] == current_user.id:
        flash("You can't buy your own listing.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    price = float(listing["sale_price"])
    buyer = db.query_one(
        "SELECT wallet_balance FROM Users WHERE user_id = %s",
        (current_user.id,),
    )
    if float(buyer["wallet_balance"]) < price:
        flash(f"Insufficient wallet balance (${price:.2f} required).", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    # the site keeps a 5% fee, the seller gets the rest
    fee         = round(price * 0.05, 2)
    seller_nets = round(price - fee, 2)

    # Everything in tx runs as one transaction, so if any step fails
    # nothing gets saved and nobody loses money.
    def tx(cur):
        cur.execute(
            "UPDATE Listings SET status='sold' "
            " WHERE listing_id=%s AND status='active'",
            (listing_id,),
        )
        # if no row changed, someone else bought it a moment before us
        if cur.rowcount != 1:
            raise RuntimeError("Listing was taken before we could complete.")
        cur.execute(
            "UPDATE Inventory SET user_id=%s WHERE inventory_id=%s",
            (current_user.id, listing["inventory_id"]),
        )
        cur.execute(
            "UPDATE Users SET wallet_balance = wallet_balance - %s "
            " WHERE user_id=%s",
            (price, current_user.id),
        )
        cur.execute(
            "UPDATE Users SET wallet_balance = wallet_balance + %s "
            " WHERE user_id=%s",
            (seller_nets, listing["seller_id"]),
        )
        cur.execute(
            "INSERT INTO Transactions "
            "  (listing_id, buyer_id, seller_id, final_price, platform_fee) "
            "VALUES (%s, %s, %s, %s, %s)",
            (listing_id, current_user.id, listing["seller_id"], price, fee),
        )

    try:
        db.run_txn(tx)
        flash("Purchase complete. Check your inventory.", "success")
    except Exception as e:
        flash(f"Purchase failed: {e}", "error")
    return redirect(url_for("my_inventory"))


@app.route("/listing/<int:listing_id>/rent", methods=["POST"])
@login_required
def rent_listing(listing_id):
    # The skin goes back to the owner on its own when end_date passes.
    # That part is done by the MySQL event at the bottom of schema.sql.
    try:
        days = int(request.form.get("days", "0"))
    except ValueError:
        flash("Invalid rental duration.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    listing = db.query_one(
        "SELECT * FROM Listings WHERE listing_id = %s",
        (listing_id,),
    )
    if not listing or listing["status"] != "active" \
            or listing["listing_type"] != "rental":
        flash("That rental is no longer available.", "error")
        return redirect(url_for("home"))
    if listing["seller_id"] == current_user.id:
        flash("You can't rent your own listing.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))
    if not (1 <= days <= int(listing["max_rental_days"])):
        flash(f"Days must be between 1 and {listing['max_rental_days']}.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    daily   = float(listing["daily_rental_rate"])
    deposit = float(listing["rental_deposit"])
    total   = round(daily * days + deposit, 2)

    wallet = db.query_one(
        "SELECT wallet_balance FROM Users WHERE user_id=%s",
        (current_user.id,),
    )
    if float(wallet["wallet_balance"]) < total:
        flash(f"Need ${total:.2f} to start this rental.", "error")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    start = date.today()
    end   = start + timedelta(days=days)

    def tx(cur):
        cur.execute(
            "UPDATE Listings SET status='rented' "
            " WHERE listing_id=%s AND status='active'",
            (listing_id,),
        )
        if cur.rowcount != 1:
            raise RuntimeError("Listing was claimed by someone else.")
        cur.execute(
            "UPDATE Users SET wallet_balance = wallet_balance - %s "
            " WHERE user_id=%s",
            (total, current_user.id),
        )
        cur.execute(
            "INSERT INTO Rentals "
            "  (listing_id, renter_id, owner_id, daily_rate, rental_days, "
            "   deposit_paid, start_date, end_date) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (listing_id, current_user.id, listing["seller_id"],
             daily, days, deposit, start, end),
        )

    try:
        db.run_txn(tx)
        flash(f"Rental started. It will be returned on {end.isoformat()}.", "success")
    except Exception as e:
        flash(f"Rental failed: {e}", "error")
    return redirect(url_for("my_rentals"))


@app.route("/rental/<int:rental_id>/return", methods=["POST"])
@login_required
def return_rental(rental_id):
    # Lets the renter give the skin back early and get the deposit back.
    rental = db.query_one(
        "SELECT * FROM Rentals WHERE rental_id = %s",
        (rental_id,),
    )
    if not rental or rental["renter_id"] != current_user.id:
        abort(403)
    if rental["status"] != "active":
        flash("This rental has already ended.", "error")
        return redirect(url_for("my_rentals"))

    deposit_refund = float(rental["deposit_paid"])

    def tx(cur):
        cur.execute(
            "UPDATE Rentals SET status='returned', returned_at=NOW() "
            " WHERE rental_id=%s AND status='active'",
            (rental_id,),
        )
        if cur.rowcount != 1:
            raise RuntimeError("Rental already returned.")
        cur.execute(
            "UPDATE Listings SET status='active' WHERE listing_id=%s",
            (rental["listing_id"],),
        )
        cur.execute(
            "UPDATE Users SET wallet_balance = wallet_balance + %s "
            " WHERE user_id=%s",
            (deposit_refund, current_user.id),
        )

    try:
        db.run_txn(tx)
        flash(f"Returned. ${deposit_refund:.2f} deposit refunded.", "success")
    except Exception as e:
        flash(f"Return failed: {e}", "error")
    return redirect(url_for("my_rentals"))


# price_chart.js calls this to draw the chart on the skin page
@app.route("/api/price-history/<int:skin_id>")
def api_price_history(skin_id):
    rows = db.query_all(
        "SELECT recorded_date, wear_category, avg_price "
        "  FROM v_price_trends_30d WHERE skin_id = %s "
        " ORDER BY recorded_date",
        (skin_id,),
    )
    return jsonify([{
        "date":  r["recorded_date"].isoformat(),
        "wear":  r["wear_category"],
        "price": float(r["avg_price"]),
    } for r in rows])


@app.errorhandler(404)
def not_found(_e):
    return render_template("base.html", error="404: page not found"), 404


@app.errorhandler(500)
def server_error(_e):
    return render_template("base.html", error="500: something went wrong"), 500


if __name__ == "__main__":
    app.run(debug=True) 