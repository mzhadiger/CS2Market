-- Run once. Drops + recreates v_active_listings with IDs exposed so the
-- Flask app can filter/act on view rows without a second query.
USE cs2_marketplace;

CREATE OR REPLACE VIEW v_active_listings AS
SELECT  l.listing_id, l.inventory_id, l.seller_id, l.listing_type,
        l.sale_price, l.daily_rental_rate, l.rental_deposit, l.max_rental_days,
        l.created_at,
        s.skin_id, s.name AS skin_name, s.rarity, s.collection, s.image_url,
        w.weapon_id, w.name AS weapon_name, w.weapon_type,
        i.wear_category, i.float_value, i.is_stattrak,
        u.username   AS seller_username,
        u.reputation AS seller_reputation
  FROM Listings  l
  JOIN Inventory i ON l.inventory_id = i.inventory_id
  JOIN Skins     s ON i.skin_id      = s.skin_id
  JOIN Weapons   w ON s.weapon_id    = w.weapon_id
  JOIN Users     u ON l.seller_id    = u.user_id
 WHERE l.status = 'active';