-- 1. Total behaviors, UV, items, and categories
select
    count(*) as total_behavior,
    count(distinct user_id) as uv,
    count(distinct item_id) as item_count,
    count(distinct category_id) as category_count
from user_behavior;

-- 2. Behavior type counts and share
select
     behavior_type,
     behavior_name_en,
     behavior_name_cn,
     count(*) as behavior_count,
     round(cast(count(*) as real)/sum(count(*)) over(),4) as behavior_share
from user_behavior
group by behavior_type,behavior_name_en,behavior_name_cn
ORDER BY behavior_count DESC;

-- 3. Daily active users
select date, count(distinct user_id) as dau from user_behavior group by date order by date;

-- 4. Daily purchase count and purchase users
select date,count(*) as purchase_count,count(distinct user_id) as purchase_users
from user_behavior where behavior_type='buy'
group by date order by date;

-- 5. Hourly behavior distribution
select hour,behavior_type,count(*) as behavior_count,count(distinct user_id) as active_users
from user_behavior
group by hour,behavior_type
order by hour,behavior_type;

-- 6. Top 10 categories by purchase
SELECT
    category_id,
    COUNT(*) AS purchase_count,
    COUNT(DISTINCT user_id) AS buyer_count
FROM user_behavior
WHERE behavior_type = 'buy'
GROUP BY category_id
ORDER BY purchase_count DESC, buyer_count DESC
LIMIT 10;

-- 7. Browse-to-purchase conversion rate at user level
with user_flags as (
     select
         user_id,
         max(case when behavior_type="pv" then 1 else 0 end) as has_pv,
         max(case when behavior_type="buy" then 1 else 0 end) as has_buy
     from user_behavior
     group by user_id
)
select sum(has_pv) as pv_users,sum(has_buy) as buyer_users,
       ROUND(
        CAST(SUM(has_pv * has_buy) AS REAL) / NULLIF(SUM(has_pv), 0),
        4
    ) AS browse_to_purchase_rate

from user_flags;

-- 8. Add-to-cart to purchase conversion rate at user level
WITH user_flags AS (
    SELECT
        user_id,
        MAX(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS has_buy
    FROM user_behavior
    GROUP BY user_id
)
SELECT
    SUM(has_cart) AS cart_users,
    SUM(CASE WHEN has_cart = 1 AND has_buy = 1 THEN 1 ELSE 0 END) AS cart_and_buy_users,
    ROUND(
        CAST(SUM(CASE WHEN has_cart = 1 AND has_buy = 1 THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(has_cart), 0), 4
    ) AS cart_to_purchase_rate
FROM user_flags;

-- 9. Favorite-to-purchase conversion rate at user level
WITH user_flags AS (
    SELECT
        user_id,
        MAX(CASE WHEN behavior_type = 'fav' THEN 1 ELSE 0 END) AS has_fav,
        MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS has_buy
    FROM user_behavior
    GROUP BY user_id
)
SELECT
    SUM(has_fav) AS favorite_users,
    SUM(CASE WHEN has_fav = 1 AND has_buy = 1 THEN 1 ELSE 0 END) AS favorite_and_buy_users,
    ROUND(
        CAST(SUM(CASE WHEN has_fav = 1 AND has_buy = 1 THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(has_fav), 0), 4
    ) AS favorite_to_purchase_rate
FROM user_flags;

-- 10. User repurchase rate
with user_purchase as (
     select user_id,count(*) as purchase_count from user_behavior where behavior_type = 'buy' group by user_id
)
select count(*) as total_buyers,sum(case when purchase_count>=2 then 1 else 0 end) as repurchase_users,
       round(
           cast(sum(case when purchase_count>=2 then 1 else 0 end) as real)/nullif(count(*),0),4
       ) as repurchase_rate
from user_purchase;

-- 11. Users who added to cart but did not purchase
WITH user_flags AS (
    SELECT
        user_id,
        MAX(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS has_buy
    FROM user_behavior
    GROUP BY user_id
)
SELECT
    COUNT(*) AS cart_without_purchase_users
FROM user_flags
WHERE has_cart = 1 AND has_buy = 0;

-- 12. High-value users Top 20
SELECT
    user_id,
    SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS purchase_count,
    COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN item_id END) AS distinct_items_bought,
    COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN category_id END) AS distinct_categories_bought,
    COUNT(DISTINCT date) AS active_days,
    (
        SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) * 5
        + COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN item_id END) * 2
        + COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN category_id END)
        + COUNT(DISTINCT date)
    ) AS value_score
FROM user_behavior
GROUP BY user_id
HAVING SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) > 0
ORDER BY value_score DESC, purchase_count DESC
LIMIT 20;

-- 13. User behavior funnel with CTE
WITH user_funnel AS (
    SELECT
        user_id,
        MAX(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS viewed,
        MAX(CASE WHEN behavior_type = 'fav' THEN 1 ELSE 0 END) AS favorited,
        MAX(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS added_to_cart,
        MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS purchased
    FROM user_behavior
    GROUP BY user_id
),
funnel_steps AS (
    SELECT '01_viewed' AS step, COUNT(*) AS users FROM user_funnel WHERE viewed = 1
    UNION ALL
    SELECT '02_favorited' AS step, COUNT(*) AS users FROM user_funnel WHERE viewed = 1 AND favorited = 1
    UNION ALL
    SELECT '03_added_to_cart' AS step, COUNT(*) AS users FROM user_funnel WHERE viewed = 1 AND added_to_cart = 1
    UNION ALL
    SELECT '04_purchased' AS step, COUNT(*) AS users FROM user_funnel WHERE viewed = 1 AND purchased = 1
)
SELECT
    step,
    users,
    ROUND(CAST(users AS REAL) / FIRST_VALUE(users) OVER (ORDER BY step), 4) AS conversion_from_view
FROM funnel_steps
ORDER BY step;

-- 14. Window function: highest purchase category by day
WITH daily_category_purchase AS (
    SELECT
        date,
        category_id,
        COUNT(*) AS purchase_count
    FROM user_behavior
    WHERE behavior_type = 'buy'
    GROUP BY date, category_id
),
ranked AS (
    SELECT
        date,
        category_id,
        purchase_count,
        DENSE_RANK() OVER (PARTITION BY date ORDER BY purchase_count DESC) AS purchase_rank
    FROM daily_category_purchase
)
SELECT
    date,
    category_id,
    purchase_count
FROM ranked
WHERE purchase_rank = 1
ORDER BY date, category_id;


-- 15. Stricter user-item sequential funnel
WITH first_events AS (
    SELECT
        user_id,
        item_id,
        MIN(CASE WHEN behavior_type = 'pv' THEN behavior_time END) AS pv_time,
        MIN(CASE WHEN behavior_type = 'fav' THEN behavior_time END) AS fav_time,
        MIN(CASE WHEN behavior_type = 'cart' THEN behavior_time END) AS cart_time,
        MIN(CASE WHEN behavior_type = 'buy' THEN behavior_time END) AS buy_time
    FROM user_behavior
    GROUP BY user_id, item_id
)
SELECT
    COUNT(*) AS user_item_pairs,
    SUM(CASE WHEN pv_time IS NOT NULL THEN 1 ELSE 0 END) AS viewed_pairs,
    SUM(CASE WHEN cart_time IS NOT NULL THEN 1 ELSE 0 END) AS carted_pairs,
    SUM(CASE WHEN buy_time IS NOT NULL THEN 1 ELSE 0 END) AS bought_pairs,
    SUM(CASE WHEN pv_time IS NOT NULL AND cart_time >= pv_time THEN 1 ELSE 0 END) AS pv_to_cart_pairs,
    SUM(CASE WHEN pv_time IS NOT NULL AND buy_time >= pv_time THEN 1 ELSE 0 END) AS pv_to_buy_pairs,
    SUM(CASE WHEN cart_time IS NOT NULL AND buy_time >= cart_time THEN 1 ELSE 0 END) AS cart_to_buy_pairs,
    SUM(CASE WHEN fav_time IS NOT NULL AND buy_time >= fav_time THEN 1 ELSE 0 END) AS fav_to_buy_pairs,
    ROUND(
        CAST(SUM(CASE WHEN pv_time IS NOT NULL AND buy_time >= pv_time THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN pv_time IS NOT NULL THEN 1 ELSE 0 END), 0), 4
    ) AS pv_to_buy_pair_rate,
    ROUND(
        CAST(SUM(CASE WHEN cart_time IS NOT NULL AND buy_time >= cart_time THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN cart_time IS NOT NULL THEN 1 ELSE 0 END), 0), 4
    ) AS cart_to_buy_pair_rate,
    ROUND(
        CAST(SUM(CASE WHEN fav_time IS NOT NULL AND buy_time >= fav_time THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN fav_time IS NOT NULL THEN 1 ELSE 0 END), 0), 4
    ) AS fav_to_buy_pair_rate
FROM first_events;

-- 16. Category-level conversion analysis
SELECT
    category_id,
    SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS pv_count,
    SUM(CASE WHEN behavior_type = 'fav' THEN 1 ELSE 0 END) AS fav_count,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart_count,
    SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS buy_count,
    ROUND(
        CAST(SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END), 0), 4
    ) AS browse_to_buy_rate,
    ROUND(
        CAST(SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END), 0), 4
    ) AS cart_to_buy_rate
FROM user_behavior
GROUP BY category_id
HAVING SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) >= 30
ORDER BY buy_count DESC, browse_to_buy_rate DESC
LIMIT 20;