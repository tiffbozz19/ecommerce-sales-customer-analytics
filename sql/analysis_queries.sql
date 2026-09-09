-- 1. Overall merchandise KPIs
SELECT
    ROUND(SUM(Revenue), 2) AS TotalRevenue,
    COUNT(DISTINCT InvoiceNo) AS TotalOrders,
    SUM(Quantity) AS UnitsSold,
    ROUND(
        SUM(Revenue) / COUNT(DISTINCT InvoiceNo),
        2
    ) AS AverageOrderValue
FROM sales;

-- 2. Monthly revenue and order trend
SELECT
    YearMonth,
    ROUND(SUM(Revenue), 2) AS Revenue,
    COUNT(DISTINCT InvoiceNo) AS Orders
FROM sales
GROUP BY YearMonth
ORDER BY YearMonth;

-- 3. Top 10 products by revenue
SELECT
    StockCode,
    ProductName,
    ROUND(SUM(Revenue), 2) AS Revenue,
    SUM(Quantity) AS UnitsSold,
    COUNT(DISTINCT InvoiceNo) AS Orders
FROM sales
GROUP BY StockCode, ProductName
ORDER BY Revenue DESC
LIMIT 10;

-- 4. Top 10 products by units sold
SELECT
    StockCode,
    ProductName,
    SUM(Quantity) AS UnitsSold,
    ROUND(SUM(Revenue), 2) AS Revenue,
    COUNT(DISTINCT InvoiceNo) AS Orders
FROM sales
GROUP BY StockCode, ProductName
ORDER BY UnitsSold DESC
LIMIT 10;

-- 5. Top markets by revenue
SELECT
    Country,
    ROUND(SUM(Revenue), 2) AS Revenue,
    COUNT(DISTINCT InvoiceNo) AS Orders,
    COUNT(DISTINCT CustomerID) AS Customers,
    ROUND(
        SUM(Revenue) / COUNT(DISTINCT InvoiceNo),
        2
    ) AS AverageOrderValue
FROM sales
GROUP BY Country
ORDER BY Revenue DESC
LIMIT 15;

-- 6. Top international markets
SELECT
    Country,
    ROUND(SUM(Revenue), 2) AS Revenue,
    COUNT(DISTINCT InvoiceNo) AS Orders,
    ROUND(
        SUM(Revenue) / COUNT(DISTINCT InvoiceNo),
        2
    ) AS AverageOrderValue
FROM sales
WHERE Country <> 'United Kingdom'
GROUP BY Country
ORDER BY Revenue DESC
LIMIT 10;

-- 7. Repeat vs one-time customers
WITH customer_orders AS (
    SELECT
        CustomerID,
        COUNT(DISTINCT InvoiceNo) AS OrderCount,
        SUM(Revenue) AS CustomerRevenue
    FROM sales
    WHERE CustomerID IS NOT NULL
    GROUP BY CustomerID
)

SELECT
    CASE
        WHEN OrderCount > 1 THEN 'Repeat Customer'
        ELSE 'One-Time Customer'
    END AS CustomerType,
    COUNT(*) AS Customers,
    ROUND(SUM(CustomerRevenue), 2) AS Revenue,
    ROUND(AVG(CustomerRevenue), 2) AS AvgRevenuePerCustomer
FROM customer_orders
GROUP BY CustomerType;

-- 8. Revenue by RFM segment
SELECT
    Segment,
    COUNT(*) AS Customers,
    ROUND(SUM(Monetary), 2) AS Revenue,
    ROUND(AVG(Monetary), 2) AS AvgCustomerRevenue,
    ROUND(AVG(Frequency), 2) AS AvgOrders,
    ROUND(AVG(Recency), 1) AS AvgRecencyDays
FROM customer_segments
GROUP BY Segment
ORDER BY Revenue DESC;