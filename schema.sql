-- =====================================================================
-- CS2 SKIN MARKETPLACE — Database Schema
-- CSCI 300 Database Management, Spring 2026
-- =====================================================================

DROP DATABASE IF EXISTS cs2_marketplace;
CREATE DATABASE cs2_marketplace
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE cs2_marketplace;

-- ---------------------------------------------------------------------
-- 1) Users — accounts that can own, buy, sell, and rent skins.
--    wallet_balance lets us demo transactions without real money.
-- ---------------------------------------------------------------------
CREATE TABLE Users (
    user_id         INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50)   NOT NULL UNIQUE,
    email           VARCHAR(100)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,
    steam_id        VARCHAR(50)   UNIQUE,
    wallet_balance  DECIMAL(12,2) NOT NULL DEFAULT 0.00
                    CHECK (wallet_balance >= 0),
    reputation      INT           NOT NULL DEFAULT 0,
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email    (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2) Weapons — base weapons (AK-47, AWP, Karambit...). Skins belong to weapons.
-- ---------------------------------------------------------------------
CREATE TABLE Weapons (
    weapon_id       INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    weapon_type     ENUM('rifle','pistol','smg','shotgun','sniper',
                         'knife','gloves','machinegun') NOT NULL,
    team            ENUM('T','CT','Both') NOT NULL DEFAULT 'Both',
    INDEX idx_type  (weapon_type)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3) Skins — weapon finishes (AK-47 Redline, AWP Dragon Lore...).
-- ---------------------------------------------------------------------
CREATE TABLE Skins (
    skin_id         INT AUTO_INCREMENT PRIMARY KEY,
    weapon_id       INT           NOT NULL,
    name            VARCHAR(150)  NOT NULL,
    rarity          ENUM('Consumer','Industrial','Mil-Spec','Restricted',
                         'Classified','Covert','Contraband',
                         'Exceedingly Rare') NOT NULL,
    collection      VARCHAR(150),
    base_price      DECIMAL(12,2) NOT NULL DEFAULT 0.00
                    CHECK (base_price >= 0),
    image_url       TEXT,
    has_stattrak    BOOLEAN       NOT NULL DEFAULT FALSE,
    has_souvenir    BOOLEAN       NOT NULL DEFAULT FALSE,
    UNIQUE KEY uq_weapon_skin (weapon_id, name),
    CONSTRAINT fk_skin_weapon
        FOREIGN KEY (weapon_id) REFERENCES Weapons(weapon_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_rarity     (rarity),
    INDEX idx_collection (collection)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4) Inventory — specific skin *instances* owned by users.
--    float_value and wear_category describe the individual item's condition.
--    paint_seed is the CS2 pattern index (0–1000).
-- ---------------------------------------------------------------------
CREATE TABLE Inventory (
    inventory_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    skin_id         INT NOT NULL,
    float_value     DECIMAL(20,18) NOT NULL
                    CHECK (float_value >= 0 AND float_value <= 1),
    wear_category   ENUM('Factory New','Minimal Wear','Field-Tested',
                         'Well-Worn','Battle-Scarred') NOT NULL,
    is_stattrak     BOOLEAN   NOT NULL DEFAULT FALSE,
    paint_seed      INT       CHECK (paint_seed BETWEEN 0 AND 1000),
    acquired_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_user
        FOREIGN KEY (user_id) REFERENCES Users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_inv_skin
        FOREIGN KEY (skin_id) REFERENCES Skins(skin_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_skin (skin_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5) Listings — inventory items made available for SALE or RENTAL.
--    listing_type drives which price columns must be populated (CHECK below).
-- ---------------------------------------------------------------------
CREATE TABLE Listings (
    listing_id         INT AUTO_INCREMENT PRIMARY KEY,
    inventory_id       INT NOT NULL,
    seller_id          INT NOT NULL,
    listing_type       ENUM('sale','rental') NOT NULL,
    sale_price         DECIMAL(12,2) CHECK (sale_price IS NULL OR sale_price >= 0),
    daily_rental_rate  DECIMAL(12,2) CHECK (daily_rental_rate IS NULL OR daily_rental_rate >= 0),
    rental_deposit     DECIMAL(12,2) CHECK (rental_deposit IS NULL OR rental_deposit >= 0),
    max_rental_days    INT           CHECK (max_rental_days IS NULL OR max_rental_days > 0),
    status             ENUM('active','sold','rented','cancelled','expired')
                       NOT NULL DEFAULT 'active',
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at         TIMESTAMP NULL,
    -- Sale listings need a sale_price; rental listings need all three rental fields.
    CONSTRAINT chk_listing_prices CHECK (
        (listing_type = 'sale'   AND sale_price IS NOT NULL)
        OR
        (listing_type = 'rental' AND daily_rental_rate IS NOT NULL
                                AND rental_deposit    IS NOT NULL
                                AND max_rental_days   IS NOT NULL)
    ),
    CONSTRAINT fk_listing_inventory
        FOREIGN KEY (inventory_id) REFERENCES Inventory(inventory_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_listing_seller
        FOREIGN KEY (seller_id)    REFERENCES Users(user_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_status (status),
    INDEX idx_type   (listing_type)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6) Transactions — completed sales only. Rentals live in their own table.
-- ---------------------------------------------------------------------
CREATE TABLE Transactions (
    transaction_id  INT AUTO_INCREMENT PRIMARY KEY,
    listing_id      INT NOT NULL,
    buyer_id        INT NOT NULL,
    seller_id       INT NOT NULL,
    final_price     DECIMAL(12,2) NOT NULL CHECK (final_price  >= 0),
    platform_fee    DECIMAL(12,2) NOT NULL DEFAULT 0.00
                    CHECK (platform_fee >= 0),
    completed_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_txn_listing
        FOREIGN KEY (listing_id) REFERENCES Listings(listing_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_txn_buyer
        FOREIGN KEY (buyer_id)   REFERENCES Users(user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_txn_seller
        FOREIGN KEY (seller_id)  REFERENCES Users(user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT chk_txn_parties CHECK (buyer_id <> seller_id),
    INDEX idx_buyer     (buyer_id),
    INDEX idx_seller    (seller_id),
    INDEX idx_completed (completed_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7) Rentals — OUR DIFFERENTIATOR.
--    A renter borrows a skin for N days. end_date is *generated* from
--    start_date + rental_days so it's impossible to get out of sync.
--    total_cost is a STORED generated column = daily_rate * rental_days.
--    Auto-return is handled by ev_auto_return_rentals below.
-- ---------------------------------------------------------------------
CREATE TABLE Rentals (
    rental_id       INT AUTO_INCREMENT PRIMARY KEY,
    listing_id      INT NOT NULL,
    renter_id       INT NOT NULL,
    owner_id        INT NOT NULL,
    daily_rate      DECIMAL(12,2) NOT NULL CHECK (daily_rate   >= 0),
    rental_days     INT           NOT NULL CHECK (rental_days  > 0),
    deposit_paid    DECIMAL(12,2) NOT NULL CHECK (deposit_paid >= 0),
    total_cost      DECIMAL(12,2) GENERATED ALWAYS AS (daily_rate * rental_days) STORED,
    start_date      DATE          NOT NULL,
    end_date        DATE          NOT NULL,
    status          ENUM('active','returned','overdue','cancelled') NOT NULL DEFAULT 'active',
    returned_at     TIMESTAMP     NULL,
    CONSTRAINT fk_rental_listing
        FOREIGN KEY (listing_id) REFERENCES Listings(listing_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_rental_renter
        FOREIGN KEY (renter_id)  REFERENCES Users(user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_rental_owner
        FOREIGN KEY (owner_id)   REFERENCES Users(user_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT chk_rental_parties CHECK (renter_id <> owner_id),
    CONSTRAINT chk_rental_dates   CHECK (end_date >= start_date),
    INDEX idx_renter   (renter_id),
    INDEX idx_owner    (owner_id),
    INDEX idx_status   (status),
    INDEX idx_end_date (end_date)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8) PriceHistory — one row per (skin, wear, date). Powers Chart.js charts.
-- ---------------------------------------------------------------------
CREATE TABLE PriceHistory (
    history_id      INT AUTO_INCREMENT PRIMARY KEY,
    skin_id         INT NOT NULL,
    wear_category   ENUM('Factory New','Minimal Wear','Field-Tested',
                         'Well-Worn','Battle-Scarred') NOT NULL,
    avg_price       DECIMAL(12,2) NOT NULL CHECK (avg_price    >= 0),
    sales_volume    INT           NOT NULL DEFAULT 0
                    CHECK (sales_volume >= 0),
    recorded_date   DATE          NOT NULL,
    UNIQUE KEY uq_skin_wear_date (skin_id, wear_category, recorded_date),
    CONSTRAINT fk_price_skin
        FOREIGN KEY (skin_id) REFERENCES Skins(skin_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_date (recorded_date)
) ENGINE=InnoDB;

-- =====================================================================
-- VIEWS — spec requires views; these map 1:1 to frontend pages.
-- =====================================================================

-- V1: Main page / search results — everything the grid needs in one query.
CREATE OR REPLACE VIEW v_active_listings AS
SELECT  l.listing_id, l.listing_type,
        l.sale_price, l.daily_rental_rate, l.rental_deposit, l.max_rental_days,
        l.created_at,
        w.name  AS weapon_name, w.weapon_type,
        s.name  AS skin_name,   s.rarity, s.collection, s.image_url,
        i.wear_category, i.float_value, i.is_stattrak,
        u.username   AS seller_username,
        u.reputation AS seller_reputation
  FROM Listings  l
  JOIN Inventory i ON l.inventory_id = i.inventory_id
  JOIN Skins     s ON i.skin_id      = s.skin_id
  JOIN Weapons   w ON s.weapon_id    = w.weapon_id
  JOIN Users     u ON l.seller_id    = u.user_id
 WHERE l.status = 'active';

-- V2: Rental status computed live against TODAY — the auto-return logic in SQL.
CREATE OR REPLACE VIEW v_rental_status AS
SELECT  r.rental_id, r.listing_id,
        u_renter.username AS renter,
        u_owner.username  AS owner,
        s.name            AS skin_name,
        w.name            AS weapon_name,
        r.start_date, r.end_date,
        DATEDIFF(r.end_date, CURDATE()) AS days_remaining,
        r.total_cost, r.deposit_paid,
        CASE
          WHEN r.status = 'returned'    THEN 'returned'
          WHEN r.status = 'cancelled'   THEN 'cancelled'
          WHEN CURDATE() >  r.end_date  THEN 'overdue'
          WHEN CURDATE() <= r.end_date  THEN 'active'
        END AS effective_status
  FROM Rentals   r
  JOIN Users     u_renter ON r.renter_id  = u_renter.user_id
  JOIN Users     u_owner  ON r.owner_id   = u_owner.user_id
  JOIN Listings  l        ON r.listing_id = l.listing_id
  JOIN Inventory i        ON l.inventory_id = i.inventory_id
  JOIN Skins     s        ON i.skin_id    = s.skin_id
  JOIN Weapons   w        ON s.weapon_id  = w.weapon_id;

-- V3: User's inventory with weapon/skin metadata — profile page.
CREATE OR REPLACE VIEW v_user_inventory AS
SELECT  i.inventory_id, u.user_id, u.username,
        w.name  AS weapon_name,
        s.name  AS skin_name, s.rarity, s.collection, s.image_url,
        i.float_value, i.wear_category, i.is_stattrak,
        s.base_price AS estimated_value,
        i.acquired_at
  FROM Inventory i
  JOIN Users   u ON i.user_id   = u.user_id
  JOIN Skins   s ON i.skin_id   = s.skin_id
  JOIN Weapons w ON s.weapon_id = w.weapon_id;

-- V4: 30-day price series per skin — feeds Chart.js on the skin detail page.
CREATE OR REPLACE VIEW v_price_trends_30d AS
SELECT  ph.skin_id,
        s.name AS skin_name,
        w.name AS weapon_name,
        ph.wear_category, ph.recorded_date,
        ph.avg_price, ph.sales_volume
  FROM PriceHistory ph
  JOIN Skins   s ON ph.skin_id  = s.skin_id
  JOIN Weapons w ON s.weapon_id = w.weapon_id
 WHERE ph.recorded_date >= CURDATE() - INTERVAL 30 DAY
 ORDER BY ph.skin_id, ph.wear_category, ph.recorded_date;

-- V5: KPI summary for landing page — one-row dashboard.
CREATE OR REPLACE VIEW v_marketplace_stats AS
SELECT
    (SELECT COUNT(*) FROM Users)                                       AS total_users,
    (SELECT COUNT(*) FROM Skins)                                       AS total_skins,
    (SELECT COUNT(*) FROM Listings WHERE status='active')              AS active_listings,
    (SELECT COUNT(*) FROM Listings WHERE status='active'
                                     AND listing_type='rental')        AS active_rental_listings,
    (SELECT COUNT(*) FROM Rentals  WHERE status='active')              AS active_rentals,
    (SELECT COALESCE(SUM(final_price),0) FROM Transactions
       WHERE completed_at >= CURDATE() - INTERVAL 30 DAY)              AS sales_volume_30d,
    (SELECT COALESCE(SUM(total_cost),0)  FROM Rentals
       WHERE start_date  >= CURDATE() - INTERVAL 30 DAY)               AS rental_volume_30d;

-- =====================================================================
-- AUTO-RETURN SCHEDULED EVENT — the "magic" behind rental auto-return.
-- Runs hourly: marks expired rentals as 'returned' and frees their listings.
-- =====================================================================
SET GLOBAL event_scheduler = ON;

DROP EVENT IF EXISTS ev_auto_return_rentals;

DELIMITER $$
CREATE EVENT ev_auto_return_rentals
ON SCHEDULE EVERY 1 HOUR
DO
BEGIN
    -- 1. Expired active rentals → returned
    UPDATE Rentals
       SET status      = 'returned',
           returned_at = NOW()
     WHERE status      = 'active'
       AND end_date    < CURDATE();

    -- 2. Reopen the listings so the owner can re-list
    UPDATE Listings L
       JOIN Rentals  R ON R.listing_id = L.listing_id
        SET L.status = 'active'
      WHERE L.status = 'rented'
        AND R.status = 'returned'
        AND R.returned_at IS NOT NULL;
END$$
DELIMITER ;
