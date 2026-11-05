-- The seed data was made on April 21, 2026. The price chart and the home page
-- only look at the last 30 days, so after a while they show nothing.
-- This moves every date forward so the data looks like it's from the last few weeks.
--
-- Run it right after seed_data.sql. It's safe to run again later, it only
-- moves the dates by how much time has passed since the last run.
USE cs2_marketplace;

-- The newest price in the seed data is always from yesterday,
-- so this is how many days we need to move everything.
SET @days = (SELECT DATEDIFF(CURDATE(), MAX(recorded_date)) - 1 FROM PriceHistory);

-- ORDER BY DESC moves the newest rows first. Without it the UNIQUE key on
-- (skin_id, wear_category, recorded_date) can complain halfway through.
UPDATE PriceHistory
   SET recorded_date = recorded_date + INTERVAL @days DAY
 WHERE @days > 0
 ORDER BY recorded_date DESC;

UPDATE Listings
   SET created_at = created_at + INTERVAL @days DAY,
       expires_at = expires_at + INTERVAL @days DAY
 WHERE @days > 0;

UPDATE Transactions
   SET completed_at = completed_at + INTERVAL @days DAY
 WHERE @days > 0;

UPDATE Rentals
   SET start_date  = start_date  + INTERVAL @days DAY,
       end_date    = end_date    + INTERVAL @days DAY,
       returned_at = returned_at + INTERVAL @days DAY
 WHERE @days > 0;

SELECT @days AS days_moved;
