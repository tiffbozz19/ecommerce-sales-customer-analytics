import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sqlite3

df = pd.read_excel("Online Retail.xlsx")

df.to_csv("online_retail.csv", index=False)

df = pd.read_csv("online_retail.csv")

df.head()
df.shape
df.info()
df.describe()
df.isnull().sum()
df.duplicated().sum()

df.head(10)
df.tail(10)

# ----------------------------------
# DATA QUALITY CHECKS
# ----------------------------------

print("\nMissing Values:")
print(df.isnull().sum())

print("\nDuplicate Rows:")
print(df.duplicated().sum())

print("\nNegative Quantities:")
print((df["Quantity"] < 0).sum())

print("\nZero Quantities:")
print((df["Quantity"] == 0).sum())

print("\nNegative Prices:")
print((df["UnitPrice"] < 0).sum())

print("\nZero Prices:")
print((df["UnitPrice"] == 0).sum())

print("\nCancelled Invoices:")
print(df["InvoiceNo"].str.startswith("C").sum())

df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

print("\nDate Range:")
print("First transaction:", df["InvoiceDate"].min())
print("Last transaction:", df["InvoiceDate"].max())

print("\nSample Negative Quantity Rows:")
print(df[df["Quantity"] < 0].head(10))

print("\nSample Zero Price Rows:")
print(df[df["UnitPrice"] == 0].head(10))

print("\nSample Missing CustomerID Rows:")
print(df[df["CustomerID"].isnull()].head(10))


# ----------------------------------
# CLEANING AND PREPROCESSING
# ----------------------------------

# Preserve original imported data
raw_df = df.copy()

# Remove exact duplicate rows
df = df.drop_duplicates().copy()

print("Rows before removing duplicates:", len(raw_df))
print("Rows after removing duplicates:", len(df))
print("Duplicates removed:", len(raw_df) - len(df))

df["CustomerID"] = df["CustomerID"].astype("Int64")

# Investigate cancelled transactions
cancelled_df = df[
    df["InvoiceNo"].str.startswith("C", na=False)
].copy()

print("Cancelled transaction rows:", len(cancelled_df))

#Investigate negative quantity rows that are not cancelled transactions
negative_non_cancelled = df[
    (df["Quantity"] < 0) &
    (~df["InvoiceNo"].str.startswith("C", na=False))
].copy()

print("Negative quantity rows without C invoice:",
      len(negative_non_cancelled))

print(negative_non_cancelled.head(20).to_string())

#Investigate negative price rows
negative_price_rows = df[df["UnitPrice"] < 0]

print(negative_price_rows.to_string())

# CLEANING DECISION:
# For revenue and sales analysis, valid sales are defined as
# transactions with positive quantity and positive unit price
# that are not cancellation invoices.
#
# Transactions without CustomerID are retained because they
# still represent valid sales, but they will be excluded from
# customer-level analyses.

sales_df = df[
    (df["Quantity"] > 0) &
    (df["UnitPrice"] > 0) &
    (~df["InvoiceNo"].str.startswith("C", na=False))
].copy()

print("Raw rows:", len(raw_df))
print("Clean sales rows:", len(sales_df))

sales_df["Revenue"] = (
    sales_df["Quantity"] * sales_df["UnitPrice"]
)

print(sales_df[
    ["InvoiceNo", "Description", "Quantity",
     "UnitPrice", "Revenue"]
].head(10))

print(negative_non_cancelled.head(20).to_string())

print(negative_price_rows.to_string())

# ----------------------------------
# VALIDATE CLEAN SALES DATA
# ----------------------------------

print("\nClean Sales Validation")
print("----------------------")

print("Rows:", len(sales_df))
print("Negative quantities:", (sales_df["Quantity"] < 0).sum())
print("Zero quantities:", (sales_df["Quantity"] == 0).sum())
print("Negative prices:", (sales_df["UnitPrice"] < 0).sum())
print("Zero prices:", (sales_df["UnitPrice"] == 0).sum())
print("Cancelled invoices:",
      sales_df["InvoiceNo"].str.startswith("C", na=False).sum())

print("\nMissing Values:")
print(sales_df.isnull().sum())

#Create a separate DataFrame for customer-level analysis, excluding rows without CustomerID
customer_df = sales_df[
    sales_df["CustomerID"].notna()
].copy()

print("\nSales rows:", len(sales_df))
print("Customer analysis rows:", len(customer_df))
print("Unique customers:", customer_df["CustomerID"].nunique())

sales_df["Year"] = sales_df["InvoiceDate"].dt.year
sales_df["Month"] = sales_df["InvoiceDate"].dt.month
sales_df["MonthName"] = sales_df["InvoiceDate"].dt.month_name()
sales_df["YearMonth"] = sales_df["InvoiceDate"].dt.to_period("M")
sales_df["DayOfWeek"] = sales_df["InvoiceDate"].dt.day_name()
sales_df["Hour"] = sales_df["InvoiceDate"].dt.hour

customer_df = sales_df[
    sales_df["CustomerID"].notna()
].copy()

#How does revenue change over time?
monthly_revenue = (
    sales_df
    .groupby("YearMonth")["Revenue"]
    .sum()
    .reset_index()
)

monthly_revenue["YearMonth"] = monthly_revenue["YearMonth"].astype(str)

print(monthly_revenue)

monthly_orders = (
    sales_df
    .groupby("YearMonth")["InvoiceNo"]
    .nunique()
    .reset_index(name="Orders")
)

print(monthly_orders)

plt.figure(figsize=(12, 6))

plt.plot(
    monthly_revenue["YearMonth"],
    monthly_revenue["Revenue"],
    marker="o"
)

plt.title("Monthly Revenue Trend")
plt.xlabel("Month")
plt.ylabel("Revenue (£)")
plt.xticks(rotation=45)
plt.tight_layout()

plt.show()

# ----------------------------------
# PRODUCT PERFORMANCE
# ----------------------------------

product_performance = (
    sales_df
    .groupby(["StockCode", "Description"])
    .agg(
        Revenue=("Revenue", "sum"),
        UnitsSold=("Quantity", "sum"),
        Orders=("InvoiceNo", "nunique")
    )
    .reset_index()
)

product_performance = product_performance.sort_values(
    "Revenue",
    ascending=False
)

print("\nTop 20 Products by Revenue:")
print(product_performance.head(20).to_string(index=False))

top_quantity = product_performance.sort_values(
    "UnitsSold",
    ascending=False
)

print("\nTop 20 Products by Units Sold:")
print(top_quantity.head(20).to_string(index=False))

total_revenue = sales_df["Revenue"].sum()
total_orders = sales_df["InvoiceNo"].nunique()
total_units = sales_df["Quantity"].sum()

average_order_value = total_revenue / total_orders

print("\nCompany Sales KPIs")
print("------------------")
print(f"Total Revenue: £{total_revenue:,.2f}")
print(f"Total Orders: {total_orders:,}")
print(f"Total Units Sold: {total_units:,}")
print(f"Average Order Value: £{average_order_value:,.2f}")

# ----------------------------------
# INVESTIGATE EXTREME PRODUCT SALES
# ----------------------------------

products_to_check = ["23843", "23166", "22502"]

for code in products_to_check:
    print(f"\nStockCode: {code}")
    print(
        sales_df[sales_df["StockCode"] == code][
            [
                "InvoiceNo",
                "StockCode",
                "Description",
                "Quantity",
                "UnitPrice",
                "CustomerID",
                "Country",
                "Revenue"
            ]
        ]
        .sort_values("Quantity", ascending=False)
        .head(10)
        .to_string(index=False)
    )

    special_codes = ["DOT", "POST", "M"]

print(
    sales_df[sales_df["StockCode"].isin(special_codes)][
        ["StockCode", "Description", "Quantity", "UnitPrice", "Revenue"]
    ]
    .groupby(["StockCode", "Description"])
    .agg(
        Revenue=("Revenue", "sum"),
        Units=("Quantity", "sum")
    )
    .reset_index()
    .to_string(index=False)
)

keywords = [
    "POSTAGE",
    "MANUAL",
    "FEE",
    "CHARGE",
    "DISCOUNT",
    "ADJUST",
    "BANK"
]

pattern = "|".join(keywords)

possible_non_products = (
    sales_df[
        sales_df["Description"]
        .str.contains(pattern, case=False, na=False)
    ][["StockCode", "Description"]]
    .drop_duplicates()
    .sort_values("StockCode")
)

print(possible_non_products.to_string(index=False))

# ----------------------------------
# CREATE MERCHANDISE DATASET
# ----------------------------------

non_merchandise_codes = [
    "DOT",
    "POST",
    "M",
    "m",
    "AMAZONFEE",
    "BANK CHARGES",
    "23574"
]

merchandise_df = sales_df[
    ~sales_df["StockCode"].isin(non_merchandise_codes)
].copy()

print("Sales rows:", len(sales_df))
print("Merchandise rows:", len(merchandise_df))

print(
    "Merchandise revenue:",
    f"£{merchandise_df['Revenue'].sum():,.2f}"
)

non_merch_revenue = (
    sales_df["Revenue"].sum()
    - merchandise_df["Revenue"].sum()
)

print(
    "Non-merchandise revenue:",
    f"£{non_merch_revenue:,.2f}"
)

# Most frequently used description for each StockCode
canonical_descriptions = (
    merchandise_df
    .groupby("StockCode")["Description"]
    .agg(lambda x: x.value_counts().index[0])
    .to_dict()
)

merchandise_df["ProductName"] = (
    merchandise_df["StockCode"]
    .map(canonical_descriptions)
)

product_performance = (
    merchandise_df
    .groupby(["StockCode", "ProductName"])
    .agg(
        Revenue=("Revenue", "sum"),
        UnitsSold=("Quantity", "sum"),
        Orders=("InvoiceNo", "nunique")
    )
    .reset_index()
)

top_revenue_products = (
    product_performance
    .sort_values("Revenue", ascending=False)
    .head(10)
)

top_unit_products = (
    product_performance
    .sort_values("UnitsSold", ascending=False)
    .head(10)
)

print("\nTop 10 Merchandise Products by Revenue:")
print(top_revenue_products.to_string(index=False))

print("\nTop 10 Merchandise Products by Units Sold:")
print(top_unit_products.to_string(index=False))

plt.figure(figsize=(10, 6))

plot_data = top_revenue_products.sort_values(
    "Revenue",
    ascending=True
)

plt.barh(
    plot_data["ProductName"],
    plot_data["Revenue"]
)

plt.title("Top 10 Products by Revenue")
plt.xlabel("Revenue (£)")
plt.ylabel("Product")
plt.tight_layout()

plt.show()

plt.figure(figsize=(10, 6))

plot_data = top_unit_products.sort_values(
    "UnitsSold",
    ascending=True
)

plt.barh(
    plot_data["ProductName"],
    plot_data["UnitsSold"]
)

plt.title("Top 10 Products by Units Sold")
plt.xlabel("Units Sold")
plt.ylabel("Product")
plt.tight_layout()

plt.show()

# ----------------------------------
# GEOGRAPHIC PERFORMANCE
# ----------------------------------

country_performance = (
    merchandise_df
    .groupby("Country")
    .agg(
        Revenue=("Revenue", "sum"),
        Orders=("InvoiceNo", "nunique"),
        UnitsSold=("Quantity", "sum"),
        Customers=("CustomerID", "nunique")
    )
    .reset_index()
    .sort_values("Revenue", ascending=False)
)

print("\nCountry Performance:")
print(country_performance.head(15).to_string(index=False))

uk_revenue = merchandise_df.loc[
    merchandise_df["Country"] == "United Kingdom",
    "Revenue"
].sum()

total_merchandise_revenue = merchandise_df["Revenue"].sum()

uk_share = uk_revenue / total_merchandise_revenue * 100

print(f"\nUK Revenue: £{uk_revenue:,.2f}")
print(f"UK Share of Merchandise Revenue: {uk_share:.1f}%")

top_countries = country_performance.head(10)

plt.figure(figsize=(10, 6))

plot_data = top_countries.sort_values("Revenue")

plt.barh(
    plot_data["Country"],
    plot_data["Revenue"]
)

plt.title("Top 10 Countries by Merchandise Revenue")
plt.xlabel("Revenue (£)")
plt.ylabel("Country")
plt.tight_layout()

plt.show()

international = (
    country_performance[
        country_performance["Country"] != "United Kingdom"
    ]
    .head(10)
)

plt.figure(figsize=(10, 6))

plot_data = international.sort_values("Revenue")

plt.barh(
    plot_data["Country"],
    plot_data["Revenue"]
)

plt.title("Top International Markets by Merchandise Revenue")
plt.xlabel("Revenue (£)")
plt.ylabel("Country")
plt.tight_layout()

plt.show()

country_performance["AverageOrderValue"] = (
    country_performance["Revenue"]
    / country_performance["Orders"]
)

print(
    country_performance[
        ["Country", "Revenue", "Orders", "AverageOrderValue"]
    ]
    .head(15)
    .to_string(index=False)
)

# ----------------------------------
# CUSTOMER ANALYSIS DATASET
# ----------------------------------

customer_merchandise_df = merchandise_df[
    merchandise_df["CustomerID"].notna()
].copy()

print("Customer transaction rows:",
      len(customer_merchandise_df))

print("Unique customers:",
      customer_merchandise_df["CustomerID"].nunique())

reference_date = (
    customer_merchandise_df["InvoiceDate"].max()
    + pd.Timedelta(days=1)
)

print("RFM reference date:", reference_date)

rfm = (
    customer_merchandise_df
    .groupby("CustomerID")
    .agg(
        LastPurchase=("InvoiceDate", "max"),
        Frequency=("InvoiceNo", "nunique"),
        Monetary=("Revenue", "sum")
    )
    .reset_index()
)

rfm["Recency"] = (
    reference_date - rfm["LastPurchase"]
).dt.days

rfm = rfm[
    [
        "CustomerID",
        "Recency",
        "Frequency",
        "Monetary",
        "LastPurchase"
    ]
]

print("\nRFM Summary:")
print(
    rfm[
        ["Recency", "Frequency", "Monetary"]
    ].describe()
)

print("\nTop 10 Customers by Revenue:")
print(
    rfm
    .sort_values("Monetary", ascending=False)
    .head(10)
    .to_string(index=False)
)

print("\nTop 10 Customers by Order Frequency:")
print(
    rfm
    .sort_values("Frequency", ascending=False)
    .head(10)
    .to_string(index=False)
)

total_customer_revenue = rfm["Monetary"].sum()

top_10_customer_revenue = (
    rfm
    .nlargest(10, "Monetary")["Monetary"]
    .sum()
)

top_10_share = (
    top_10_customer_revenue
    / total_customer_revenue
    * 100
)

print(
    f"Top 10 customers' share of identifiable "
    f"customer revenue: {top_10_share:.2f}%"
)

top_100_customer_revenue = (
    rfm
    .nlargest(100, "Monetary")["Monetary"]
    .sum()
)

top_100_share = (
    top_100_customer_revenue
    / total_customer_revenue
    * 100
)

print(
    f"Top 100 customers' share of identifiable "
    f"customer revenue: {top_100_share:.2f}%"
)

# ----------------------------------
# RFM SCORING
# ----------------------------------

# Percentile ranks
recency_pct = rfm["Recency"].rank(
    method="average",
    pct=True,
    ascending=True
)

frequency_pct = rfm["Frequency"].rank(
    method="average",
    pct=True,
    ascending=True
)

monetary_pct = rfm["Monetary"].rank(
    method="average",
    pct=True,
    ascending=True
)

# Lower recency is better, so reverse the score
rfm["R_Score"] = (
    6 - np.ceil(recency_pct * 5)
).astype(int)

# Higher frequency and monetary are better
rfm["F_Score"] = (
    np.ceil(frequency_pct * 5)
).astype(int)

rfm["M_Score"] = (
    np.ceil(monetary_pct * 5)
).astype(int)

print("\nR Score Distribution:")
print(rfm["R_Score"].value_counts().sort_index())

print("\nF Score Distribution:")
print(rfm["F_Score"].value_counts().sort_index())

print("\nM Score Distribution:")
print(rfm["M_Score"].value_counts().sort_index())

def assign_segment(row):
    r = row["R_Score"]
    f = row["F_Score"]
    m = row["M_Score"]

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"

    elif r <= 2 and f >= 4 and m >= 4:
        return "Can't Lose Them"

    elif r <= 2 and f >= 3:
        return "At Risk"

    elif r == 5 and f == 1:
        return "Recent One-Time Buyers"

    elif r >= 4 and f in [2, 3]:
        return "Potential Loyalists"

    elif r >= 3 and f >= 4:
        return "Loyal Customers"

    elif r <= 2 and f <= 2:
        return "Hibernating"

    else:
        return "Needs Attention"


rfm["Segment"] = rfm.apply(assign_segment, axis=1)

segment_summary = (
    rfm
    .groupby("Segment")
    .agg(
        Customers=("CustomerID", "count"),
        Revenue=("Monetary", "sum"),
        AvgRevenue=("Monetary", "mean"),
        AvgFrequency=("Frequency", "mean"),
        AvgRecency=("Recency", "mean")
    )
    .reset_index()
)

segment_summary["CustomerShare"] = (
    segment_summary["Customers"]
    / rfm["CustomerID"].nunique()
    * 100
)

segment_summary["RevenueShare"] = (
    segment_summary["Revenue"]
    / rfm["Monetary"].sum()
    * 100
)

segment_summary = segment_summary.sort_values(
    "Revenue",
    ascending=False
)

print(
    segment_summary[
        [
            "Segment",
            "Customers",
            "CustomerShare",
            "Revenue",
            "RevenueShare",
            "AvgFrequency",
            "AvgRecency"
        ]
    ].to_string(index=False)
)

plt.figure(figsize=(10, 6))

plot_data = segment_summary.sort_values(
    "Revenue",
    ascending=True
)

plt.barh(
    plot_data["Segment"],
    plot_data["Revenue"]
)

plt.title("Revenue by Customer Segment")
plt.xlabel("Revenue (£)")
plt.ylabel("Customer Segment")
plt.tight_layout()

plt.show()

plt.figure(figsize=(10, 6))

plot_data = segment_summary.sort_values(
    "Customers",
    ascending=True
)

plt.barh(
    plot_data["Segment"],
    plot_data["Customers"]
)

plt.title("Customers by RFM Segment")
plt.xlabel("Number of Customers")
plt.ylabel("Customer Segment")
plt.tight_layout()

plt.show()

# ----------------------------------
# REPEAT CUSTOMER ANALYSIS
# ----------------------------------

repeat_customers = (
    rfm["Frequency"] > 1
).sum()

one_time_customers = (
    rfm["Frequency"] == 1
).sum()

total_customers = len(rfm)

repeat_customer_rate = (
    repeat_customers / total_customers * 100
)

print(f"Total Customers: {total_customers:,}")
print(f"Repeat Customers: {repeat_customers:,}")
print(f"One-Time Customers: {one_time_customers:,}")
print(f"Repeat Customer Rate: {repeat_customer_rate:.1f}%")

repeat_revenue = rfm.loc[
    rfm["Frequency"] > 1,
    "Monetary"
].sum()

one_time_revenue = rfm.loc[
    rfm["Frequency"] == 1,
    "Monetary"
].sum()

total_revenue = rfm["Monetary"].sum()

print(
    f"Repeat Customer Revenue: "
    f"£{repeat_revenue:,.2f}"
)

print(
    f"Repeat Customer Revenue Share: "
    f"{repeat_revenue / total_revenue * 100:.1f}%"
)

print(
    f"One-Time Customer Revenue: "
    f"£{one_time_revenue:,.2f}"
)

# ----------------------------------
# EXPORT CLEANED DATA
# ----------------------------------

merchandise_df.to_csv(
    "online_retail_clean.csv",
    index=False
)

rfm.to_csv(
    "customer_rfm_segments.csv",
    index=False
)

product_performance.to_csv(
    "product_performance.csv",
    index=False
)

country_performance.to_csv(
    "country_performance.csv",
    index=False
)

monthly_revenue.to_csv(
    "monthly_revenue.csv",
    index=False
)

print("\nExport complete!")

# ----------------------------------
# CREATE SQLITE DATABASE
# ----------------------------------

# Create copies specifically for SQL export
sql_sales_df = merchandise_df.copy()
sql_rfm_df = rfm.copy()

# SQLite cannot store pandas Period objects,
# so convert YearMonth to text
sql_sales_df["YearMonth"] = sql_sales_df["YearMonth"].astype(str)

# Connect to database
conn = sqlite3.connect("online_retail.db")

# Export tables
sql_sales_df.to_sql(
    "sales",
    conn,
    if_exists="replace",
    index=False
)

sql_rfm_df.to_sql(
    "customer_segments",
    conn,
    if_exists="replace",
    index=False
)

conn.close()

print("SQLite database created successfully!")
