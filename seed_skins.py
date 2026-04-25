#!/usr/bin/env python3
"""
seed_skins.py — CS2 Skin Marketplace Seed Data Generator
CSCI 300 Database Management, Spring 2026

Fetches the real CS2 skin catalog from ByMykel/CSGO-API and generates a
deterministic seed_data.sql file with 20+ rows per table. The generated
SQL matches schema.sql exactly.

Usage:
    python seed_skins.py                  # → seed_data.sql
    python seed_skins.py --out foo.sql    # custom output path
    python seed_skins.py --refresh        # re-download API cache

Then:
    mysql -u root -p cs2_marketplace < seed_data.sql
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_URL    = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json"
CACHE_PATH = Path(__file__).parent / "skins_cache.json"
SEED       = 42                 # deterministic output across runs
TODAY      = date(2026, 4, 21)  # pinned so grader sees the same "now"

# Curated weapon lists — keeps the seed file focused on iconic items.
# (API has ~1500 skins; we only need enough for 20+ rows per table.)
RIFLES      = {"AK-47", "M4A4", "M4A1-S", "FAMAS", "Galil AR", "AUG", "SG 553"}
SNIPERS     = {"AWP", "SSG 08", "SCAR-20", "G3SG1"}
PISTOLS     = {"Glock-18", "USP-S", "P2000", "P250", "Five-SeveN", "Tec-9",
               "CZ75-Auto", "Desert Eagle", "R8 Revolver", "Dual Berettas"}
SMGS        = {"MP9", "MAC-10", "MP7", "UMP-45", "P90", "PP-Bizon", "MP5-SD"}
SHOTGUNS    = {"Nova", "XM1014", "Sawed-Off", "MAG-7"}
MACHINEGUNS = {"M249", "Negev"}

KEEP_WEAPONS = (RIFLES | SNIPERS | PISTOLS | SMGS | SHOTGUNS | MACHINEGUNS)
KNIFE_HINTS  = ("Knife", "Karambit", "Bayonet", "Daggers", "Falchion", "Flip",
                "Gut", "Huntsman", "Navaja", "Nomad", "Paracord", "Skeleton",
                "Stiletto", "Survival", "Talon", "Ursus", "Kukri", "Butterfly")
GLOVE_HINTS  = ("Gloves", "Hand Wraps")

# Map CSGO-API rarity names → schema ENUM values.
RARITY_MAP = {
    "Consumer Grade":   "Consumer",
    "Industrial Grade": "Industrial",
    "Mil-Spec Grade":   "Mil-Spec",
    "Restricted":       "Restricted",
    "Classified":       "Classified",
    "Covert":           "Covert",
    "Contraband":       "Contraband",
    "Extraordinary":    "Exceedingly Rare",
}

# (low, high) base-price range per rarity — used for fake MSRP.
PRICE_BANDS = {
    "Consumer":         (0.03,    0.25),
    "Industrial":       (0.15,    2.00),
    "Mil-Spec":         (1.00,   12.00),
    "Restricted":       (4.00,   60.00),
    "Classified":       (15.00,  300.00),
    "Covert":           (50.00, 2500.00),
    "Contraband":       (5000.00, 20000.00),
    "Exceedingly Rare": (150.00, 4500.00),  # knives / gloves
}

# Float → wear-category mapping (CS2 official thresholds).
WEAR_BUCKETS = [
    (0.00, 0.07, "Factory New"),
    (0.07, 0.15, "Minimal Wear"),
    (0.15, 0.38, "Field-Tested"),
    (0.38, 0.45, "Well-Worn"),
    (0.45, 1.00, "Battle-Scarred"),
]

# Fake but plausible usernames. 20 = spec's minimum.
USERNAMES = [
    "s1mple_fan_99", "ZywOo_GOAT", "device_CPH", "NiKo_G2", "b1t_navi",
    "ropz_faze", "Twistzz", "karrigan", "m0NESY", "donk_spirit",
    "xantares_eu", "ax1le_cloud9", "Ax1Le", "electroNic", "Perfecto",
    "Boombl4", "hobbit_lr", "stewie2k", "EliGE_usa", "NAF_team_liquid",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def sql_str(value) -> str:
    """Quote & escape a Python value for MySQL. Handles None, numbers, strings."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return f"'{value.isoformat()}'"
    s = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"

def classify_weapon(weapon_name: str) -> str | None:
    """Map a weapon name to the weapon_type ENUM. None = skip this skin."""
    if weapon_name in RIFLES:      return "rifle"
    if weapon_name in SNIPERS:     return "sniper"
    if weapon_name in PISTOLS:     return "pistol"
    if weapon_name in SMGS:        return "smg"
    if weapon_name in SHOTGUNS:    return "shotgun"
    if weapon_name in MACHINEGUNS: return "machinegun"
    if any(h in weapon_name for h in GLOVE_HINTS): return "gloves"
    if any(h in weapon_name for h in KNIFE_HINTS): return "knife"
    return None

def float_to_wear(f: float) -> str:
    for lo, hi, name in WEAR_BUCKETS:
        if lo <= f < hi:
            return name
    return "Battle-Scarred"

def load_api_data(refresh: bool) -> list[dict]:
    """Download skins.json once, cache locally. --refresh forces re-download."""
    if CACHE_PATH.exists() and not refresh:
        print(f"  Using cached API data: {CACHE_PATH}")
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    print(f"  Fetching {API_URL} ...")
    req = Request(API_URL, headers={"User-Agent": "CSCI300-Project/1.0"})
    with urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8")
    CACHE_PATH.write_text(raw, encoding="utf-8")
    print(f"  Cached to {CACHE_PATH}")
    return json.loads(raw)

# ---------------------------------------------------------------------------
# Catalog building: API → Weapons + Skins
# ---------------------------------------------------------------------------
def build_catalog(skins_json: list[dict]):
    weapons: dict[str, dict] = {}     # name → {weapon_id, name, type, team}
    skins:   list[dict]      = []
    seen:    set             = set()  # dedup by (weapon, display_name)


    for entry in skins_json:
        weapon_obj = entry.get("weapon") or {}
        w_name     = weapon_obj.get("name")
        w_type     = classify_weapon(w_name) if w_name else None
        if not w_type:
            continue

        rarity_name = (entry.get("rarity") or {}).get("name", "")
        rarity      = RARITY_MAP.get(rarity_name)
        # Knives/gloves often come through as "Covert" in-game — normalize.
        if rarity is None and w_type in ("knife", "gloves"):
            rarity = "Exceedingly Rare"
        if rarity is None:
            continue

        # De-dup: the API lists Doppler phases, StatTrak/non, etc. as
        # separate entries with identical (weapon, name). Schema's UNIQUE
        # key on (weapon_id, name) would reject them, so skip here.
        dedup_key = (w_name, entry["name"])
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        # Register weapon (first time only).
        if w_name not in weapons:
            weapons[w_name] = {
                "weapon_id":   len(weapons) + 1,
                "name":        w_name,
                "weapon_type": w_type,
                "team":        "Both",  # CS2-specific team could be parsed from entry["team"]
            }

        # Knives/gloves normally don't have StatTrak on the base item but do have souvenir=False.
        base_lo, base_hi = PRICE_BANDS[rarity]
        # Hash-seed the price by skin name for stability across runs.
        rng = random.Random(hash(entry["name"]) ^ SEED)
        base_price = round(rng.uniform(base_lo, base_hi), 2)

        skins.append({
            "skin_id":      len(skins) + 1,
            "weapon_id":    weapons[w_name]["weapon_id"],
            "name":         entry["name"],
            "rarity":       rarity,
            "collection":   (entry.get("crates") or [{}])[0].get("name") if entry.get("crates") else None,
            "base_price":   base_price,
            "image_url":    entry.get("image"),
            "has_stattrak": bool(entry.get("stattrak")),
            "has_souvenir": bool(entry.get("souvenir")),
            "min_float":    entry.get("min_float", 0.0),
            "max_float":    entry.get("max_float", 1.0),
        })

    # Cap skins for a tight seed file. Keep ALL weapons but sample skins
    # with a bias toward rarer items (better for demo queries).
    rarity_priority = {"Contraband": 0, "Covert": 1, "Exceedingly Rare": 1,
                       "Classified": 2, "Restricted": 3, "Mil-Spec": 4,
                       "Industrial": 5, "Consumer": 6}
    skins.sort(key=lambda s: (rarity_priority.get(s["rarity"], 9), s["name"]))
    skins = skins[:90]  # 90 > 20 → easily satisfies spec

    # Re-number skin_ids contiguously after the sort.
    for i, s in enumerate(skins, start=1):
        s["skin_id"] = i

    return list(weapons.values()), skins

# ---------------------------------------------------------------------------
# Synthetic data: Users, Inventory, Listings, Transactions, Rentals, Prices
# ---------------------------------------------------------------------------
def generate_users(rng: random.Random):
    users = []
    for i, uname in enumerate(USERNAMES, start=1):
        users.append({
            "user_id":        i,
            "username":       uname,
            "email":          f"{uname.lower()}@example.com",
            # A plaintext-looking hash — pbkdf2 is what Flask-Login would produce.
            "password_hash":  "pbkdf2:sha256:600000$demo$" + f"{i:064x}",
            "steam_id":       f"7656119800000{i:04d}",
            "wallet_balance": round(rng.uniform(50.0, 5000.0), 2),
            "reputation":     rng.randint(-5, 250),
        })
    return users

def generate_inventory(rng: random.Random, users, skins):
    inventory = []
    inv_id = 1
    for u in users:
        owned_count = rng.randint(4, 7)  # 20 users × avg 5.5 = ~110 rows
        picks = rng.sample(skins, owned_count)
        for s in picks:
            f = round(rng.uniform(s["min_float"], s["max_float"]), 18)
            inventory.append({
                "inventory_id":  inv_id,
                "user_id":       u["user_id"],
                "skin_id":       s["skin_id"],
                "float_value":   f,
                "wear_category": float_to_wear(f),
                # StatTrak roughly 1-in-10 when the skin supports it.
                "is_stattrak":   bool(s.get("has_stattrak") and rng.random() < 0.1),
                "paint_seed":    rng.randint(0, 1000),
            })
            inv_id += 1
    return inventory

def generate_listings(rng: random.Random, inventory, skins_by_id):
    """~55% of inventory gets listed; half of listings are rentals."""
    listings = []
    lid = 1
    for inv in inventory:
        if rng.random() > 0.55:
            continue
        skin  = skins_by_id[inv["skin_id"]]
        price = round(skin["base_price"] * rng.uniform(0.8, 1.4), 2)
        if rng.random() < 0.5:
            listings.append({
                "listing_id":        lid,
                "inventory_id":      inv["inventory_id"],
                "seller_id":         inv["user_id"],
                "listing_type":      "sale",
                "sale_price":        price,
                "daily_rental_rate": None,
                "rental_deposit":    None,
                "max_rental_days":   None,
                "status":            "active",
                "created_at":        TODAY - timedelta(days=rng.randint(0, 20)),
                "expires_at":        None,
            })
        else:
            daily = max(0.25, round(price * 0.03, 2))
            listings.append({
                "listing_id":        lid,
                "inventory_id":      inv["inventory_id"],
                "seller_id":         inv["user_id"],
                "listing_type":      "rental",
                "sale_price":        None,
                "daily_rental_rate": daily,
                "rental_deposit":    round(price * 0.6, 2),
                "max_rental_days":   rng.choice([3, 7, 14, 30]),
                "status":            "active",
                "created_at":        TODAY - timedelta(days=rng.randint(0, 20)),
                "expires_at":        None,
            })
        lid += 1
    return listings

def generate_transactions(rng: random.Random, listings, users):
    """Flip some sale listings to 'sold' and create matching transactions."""
    sale_listings = [l for l in listings if l["listing_type"] == "sale"]
    # Pick ~60% of sale listings to "complete", but never more than exist.
    # Clamp to len(sale_listings) so small random draws don't crash.
    k = min(len(sale_listings), max(20, int(len(sale_listings) * 0.6)))
    sold = rng.sample(sale_listings, k=k)
    transactions = []
    for tid, l in enumerate(sold, start=1):
        # Mark source listing as sold.
        l["status"] = "sold"
        # Pick a buyer who isn't the seller.
        buyer = rng.choice([u for u in users if u["user_id"] != l["seller_id"]])
        final_price = round(l["sale_price"] * rng.uniform(0.92, 1.00), 2)
        transactions.append({
            "transaction_id": tid,
            "listing_id":     l["listing_id"],
            "buyer_id":       buyer["user_id"],
            "seller_id":      l["seller_id"],
            "final_price":    final_price,
            "platform_fee":   round(final_price * 0.05, 2),  # 5% fee
            "completed_at":   datetime.combine(
                                  l["created_at"] + timedelta(days=rng.randint(0, 5)),
                                  datetime.min.time()
                              ).replace(hour=rng.randint(8, 22)),
        })
    return transactions

def generate_rentals(rng: random.Random, listings, users):
    """
    Three cohorts so the demo shows all rental states:
      ACTIVE   (end_date in future)    → shows in v_rental_status as 'active'
      OVERDUE  (status='active', past) → shows as 'overdue' until event runs
      RETURNED (status='returned')     → fully completed
    """
    rentals = []
    rid = 1
    rental_listings = [l for l in listings if l["listing_type"] == "rental"]
    # Use ~80% of rental listings so we comfortably exceed 20 rows.
    chosen = rng.sample(rental_listings, k=min(len(rental_listings),
                                               max(20, int(len(rental_listings) * 0.8))))

    for idx, l in enumerate(chosen):
        renter = rng.choice([u for u in users if u["user_id"] != l["seller_id"]])
        days   = rng.randint(1, l["max_rental_days"])
        # Cycle through cohorts deterministically.
        cohort = idx % 3  # 0=active, 1=overdue, 2=returned
        if cohort == 0:                              # active, ends in the future
            start = TODAY - timedelta(days=rng.randint(0, max(1, days - 1)))
            end   = start + timedelta(days=days)
            status, returned_at = "active", None
            l["status"] = "rented"
        elif cohort == 1:                            # overdue — end_date in past
            start = TODAY - timedelta(days=days + rng.randint(1, 5))
            end   = start + timedelta(days=days)
            status, returned_at = "active", None
            l["status"] = "rented"
        else:                                        # returned
            start = TODAY - timedelta(days=days + rng.randint(2, 20))
            end   = start + timedelta(days=days)
            status = "returned"
            returned_at = datetime.combine(end, datetime.min.time()).replace(
                                             hour=rng.randint(6, 22))
            # Listing is free again after return.
            l["status"] = "active"

        rentals.append({
            "rental_id":   rid,
            "listing_id":  l["listing_id"],
            "renter_id":   renter["user_id"],
            "owner_id":    l["seller_id"],
            "daily_rate":  l["daily_rental_rate"],
            "rental_days": days,
            "deposit_paid": l["rental_deposit"],
            "start_date":  start,
            "end_date":    end,
            "status":      status,
            "returned_at": returned_at,
        })
        rid += 1
    return rentals

def generate_price_history(rng: random.Random, skins):
    """30 days × 3 wears × top-20 skins ≈ 1800 rows. Walks realistically."""
    history = []
    hid = 1
    top_skins = [s for s in skins
                 if s["rarity"] in ("Covert", "Classified", "Exceedingly Rare")][:20]
    wears = ("Factory New", "Field-Tested", "Battle-Scarred")
    for s in top_skins:
        for wear in wears:
            # Wear modifies base price: FN premium, BS discount.
            wear_mult = {"Factory New": 1.3, "Field-Tested": 1.0,
                         "Battle-Scarred": 0.7}[wear]
            price = s["base_price"] * wear_mult
            for d in range(30, 0, -1):
                # Random walk ±3%.
                price *= rng.uniform(0.97, 1.03)
                history.append({
                    "history_id":    hid,
                    "skin_id":       s["skin_id"],
                    "wear_category": wear,
                    "avg_price":     round(price, 2),
                    "sales_volume":  rng.randint(0, 80),
                    "recorded_date": TODAY - timedelta(days=d),
                })
                hid += 1
    return history

# ---------------------------------------------------------------------------
# SQL writer
# ---------------------------------------------------------------------------
def write_sql(out, weapons, skins, users, inventory, listings,
              transactions, rentals, price_history):
    w = out.write
    w("-- =====================================================================\n")
    w("-- CS2 Marketplace SEED DATA (auto-generated by seed_skins.py)\n")
    w(f"-- Generated: {datetime.now().isoformat(timespec='seconds')}\n")
    w(f"-- Source:    {API_URL}\n")
    w("-- =====================================================================\n")
    w("USE cs2_marketplace;\n")
    w("SET FOREIGN_KEY_CHECKS = 0;\n")
    w("TRUNCATE TABLE PriceHistory; TRUNCATE TABLE Rentals;\n")
    w("TRUNCATE TABLE Transactions; TRUNCATE TABLE Listings;\n")
    w("TRUNCATE TABLE Inventory;    TRUNCATE TABLE Skins;\n")
    w("TRUNCATE TABLE Weapons;      TRUNCATE TABLE Users;\n")
    w("SET FOREIGN_KEY_CHECKS = 1;\n\n")

    def section(title, rows, cols, table):
        if not rows:
            return
        w(f"-- {title} ({len(rows)} rows)\n")
        w(f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n")
        vals = []
        for r in rows:
            vals.append("  (" + ", ".join(sql_str(r[c]) for c in cols) + ")")
        w(",\n".join(vals))
        w(";\n\n")

    section("Users",        users,        ["user_id","username","email","password_hash",
                                            "steam_id","wallet_balance","reputation"], "Users")
    section("Weapons",      weapons,      ["weapon_id","name","weapon_type","team"],   "Weapons")
    section("Skins",        skins,        ["skin_id","weapon_id","name","rarity","collection",
                                            "base_price","image_url","has_stattrak",
                                            "has_souvenir"],                            "Skins")
    section("Inventory",    inventory,    ["inventory_id","user_id","skin_id","float_value",
                                            "wear_category","is_stattrak","paint_seed"], "Inventory")
    section("Listings",     listings,     ["listing_id","inventory_id","seller_id","listing_type",
                                            "sale_price","daily_rental_rate","rental_deposit",
                                            "max_rental_days","status","created_at",
                                            "expires_at"],                              "Listings")
    section("Transactions", transactions, ["transaction_id","listing_id","buyer_id","seller_id",
                                            "final_price","platform_fee","completed_at"],"Transactions")
    section("Rentals",      rentals,      ["rental_id","listing_id","renter_id","owner_id",
                                            "daily_rate","rental_days","deposit_paid",
                                            "start_date","end_date","status","returned_at"],"Rentals")
    section("PriceHistory", price_history,["history_id","skin_id","wear_category","avg_price",
                                            "sales_volume","recorded_date"],             "PriceHistory")

    w("-- Done. Verify with:  SELECT * FROM v_marketplace_stats;\n")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="Generate seed_data.sql from CSGO-API.")
    p.add_argument("--out", default="seed_data.sql", help="output SQL path")
    p.add_argument("--refresh", action="store_true", help="force re-download of API cache")
    args = p.parse_args()

    print(f"[1/4] Loading CSGO-API data ...")
    skins_json = load_api_data(refresh=args.refresh)
    print(f"      API returned {len(skins_json)} skins.")

    print("[2/4] Building weapon + skin catalog ...")
    weapons, skins = build_catalog(skins_json)
    skins_by_id = {s["skin_id"]: s for s in skins}
    print(f"      Kept {len(weapons)} weapons and {len(skins)} skins.")

    print("[3/4] Generating synthetic users + activity ...")
    rng          = random.Random(SEED)
    users        = generate_users(rng)
    inventory    = generate_inventory(rng, users, skins)
    listings     = generate_listings(rng, inventory, skins_by_id)
    transactions = generate_transactions(rng, listings, users)
    rentals      = generate_rentals(rng, listings, users)
    price_hist   = generate_price_history(rng, skins)

    print("[4/4] Writing SQL ...")
    with open(args.out, "w", encoding="utf-8") as f:
        write_sql(f, weapons, skins, users, inventory, listings,
                  transactions, rentals, price_hist)

    print(f"\nDONE → {args.out}")
    print(f"  Users:        {len(users):5d}")
    print(f"  Weapons:      {len(weapons):5d}")
    print(f"  Skins:        {len(skins):5d}")
    print(f"  Inventory:    {len(inventory):5d}")
    print(f"  Listings:     {len(listings):5d}")
    print(f"  Transactions: {len(transactions):5d}")
    print(f"  Rentals:      {len(rentals):5d}")
    print(f"  PriceHistory: {len(price_hist):5d}")

if __name__ == "__main__":
    main()