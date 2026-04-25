-- =====================================================================
-- DEMO QUERIES — run these individually during the oral presentation.
-- Spec requires at least 5; 7 provided so you have flexibility.
-- =====================================================================
USE cs2_marketplace;

-- Q1: Filter search — powers the main page filter bar.
--     "Show me Covert/Classified rifles priced $50–$500."
SELECT  s.skin_id, w.name AS weapon, s.name AS skin,
        s.rarity, s.base_price, s.image_url
  FROM  Skins   s
  JOIN  Weapons w ON s.weapon_id = w.weapon_id
 WHERE  w.weapon_type = 'rifle'
   AND  s.rarity IN ('Covert','Classified')
   AND  s.base_price BETWEEN 50 AND 500
 ORDER  BY s.base_price DESC;

-- Q2: Top 10 most-traded skins in the last 30 days (aggregation + GROUP BY).
SELECT  s.name AS skin, w.name AS weapon,
        COUNT(t.transaction_id)     AS trades,
        ROUND(AVG(t.final_price),2) AS avg_price
  FROM  Transactions t
  JOIN  Listings   l ON t.listing_id  = l.listing_id
  JOIN  Inventory  i ON l.inventory_id = i.inventory_id
  JOIN  Skins      s ON i.skin_id      = s.skin_id
  JOIN  Weapons    w ON s.weapon_id    = w.weapon_id
 WHERE  t.completed_at >= CURDATE() - INTERVAL 30 DAY
 GROUP  BY s.skin_id
 ORDER  BY trades DESC
 LIMIT  10;

-- Q3: A user's complete inventory with estimated market value (uses V3).
SELECT * FROM v_user_inventory WHERE user_id = 1;

-- Q4: Rentals expiring in the next 3 days — target list for email alerts.
SELECT  rental_id, renter, owner, skin_name, weapon_name,
        end_date, days_remaining, effective_status
  FROM  v_rental_status
 WHERE  effective_status = 'active'
   AND  days_remaining BETWEEN 0 AND 3
 ORDER  BY end_date ASC;

-- Q5: Revenue per user — sales + rentals in one query (LEFT JOIN + subqueries).
SELECT  u.user_id, u.username,
        COALESCE(sales.sale_revenue, 0)   AS sale_revenue,
        COALESCE(rentals.rent_revenue, 0) AS rental_revenue,
        COALESCE(sales.sale_revenue, 0)
        + COALESCE(rentals.rent_revenue, 0) AS total_revenue
  FROM  Users u
  LEFT  JOIN (
        SELECT seller_id, SUM(final_price - platform_fee) AS sale_revenue
          FROM Transactions
         GROUP BY seller_id
  ) sales   ON sales.seller_id = u.user_id
  LEFT  JOIN (
        SELECT owner_id, SUM(total_cost) AS rent_revenue
          FROM Rentals
         WHERE status IN ('active','returned')
         GROUP BY owner_id
  ) rentals ON rentals.owner_id = u.user_id
 ORDER  BY total_revenue DESC;

-- Q6: 30-day price history for a specific skin — the Chart.js data feed.
SELECT  recorded_date, wear_category, avg_price, sales_volume
  FROM  v_price_trends_30d
 WHERE  skin_id = 1
 ORDER  BY recorded_date;

-- Q7: Find all Covert rifles currently available to rent under $5/day
--     — cleanly demonstrates the rental differentiator.
SELECT  listing_id, weapon_name, skin_name, wear_category,
        daily_rental_rate, rental_deposit, max_rental_days,
        seller_username
  FROM  v_active_listings
 WHERE  listing_type       = 'rental'
   AND  rarity             = 'Covert'
   AND  weapon_type        = 'rifle'
   AND  daily_rental_rate  < 5.00
 ORDER  BY daily_rental_rate ASC;