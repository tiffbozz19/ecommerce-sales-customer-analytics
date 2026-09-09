"""Portfolio pipeline for the UCI Online Retail analysis."""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "Online Retail.xlsx"
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_FILE = PROJECT_ROOT / "online_retail.db"

# Verified administrative/non-merchandise transaction codes.
NON_MERCHANDISE_CODES = {
    "DOT", "POST", "M", "m", "AMAZONFEE", "BANK CHARGES", "23574"
}


def load_data(filepath):
    """Load the retail dataset, using a CSV cache when available."""

    csv_path = PROJECT_ROOT / "online_retail.csv"

    if csv_path.exists():
        print("Loading cached CSV...")
        df = pd.read_csv(csv_path)
    else:
        print("Loading Excel file...")
        df = pd.read_excel(filepath)

        print("Creating CSV cache for faster future runs...")
        df.to_csv(csv_path, index=False)

    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["CustomerID"] = df["CustomerID"].astype("Int64")
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)

    print(f"Loaded {len(df):,} rows.")
    return df


def audit_data(df: pd.DataFrame) -> dict:
    """Capture the main raw-data quality issues."""
    return {
        "rows": len(df),
        "duplicates": int(df.duplicated().sum()),
        "missing_descriptions": int(df["Description"].isna().sum()),
        "missing_customer_ids": int(df["CustomerID"].isna().sum()),
        "negative_quantities": int((df["Quantity"] < 0).sum()),
        "zero_prices": int((df["UnitPrice"] == 0).sum()),
        "negative_prices": int((df["UnitPrice"] < 0).sum()),
        "cancelled_rows": int(
            df["InvoiceNo"].str.startswith("C", na=False).sum()
        ),
        "first_transaction": df["InvoiceDate"].min(),
        "last_transaction": df["InvoiceDate"].max(),
    }


def clean_sales_data(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates, cancellations, and invalid sales; engineer features."""
    cleaned = df.drop_duplicates().copy()

    # Missing CustomerID values stay here because they are still usable for
    # aggregate sales analysis; customer analysis filters them later.
    sales = cleaned[
        (cleaned["Quantity"] > 0)
        & (cleaned["UnitPrice"] > 0)
        & (~cleaned["InvoiceNo"].str.startswith("C", na=False))
    ].copy()

    sales["Revenue"] = sales["Quantity"] * sales["UnitPrice"]
    sales["Year"] = sales["InvoiceDate"].dt.year
    sales["Month"] = sales["InvoiceDate"].dt.month
    sales["MonthName"] = sales["InvoiceDate"].dt.month_name()
    sales["YearMonth"] = sales["InvoiceDate"].dt.to_period("M")
    sales["DayOfWeek"] = sales["InvoiceDate"].dt.day_name()
    sales["Hour"] = sales["InvoiceDate"].dt.hour
    return sales


def create_merchandise_data(sales: pd.DataFrame) -> pd.DataFrame:
    """Remove non-merchandise lines and standardize product display names."""
    merchandise = sales[
        ~sales["StockCode"].isin(NON_MERCHANDISE_CODES)
    ].copy()

    # StockCode is the product ID; descriptions are not perfectly consistent.
    canonical_names = (
        merchandise.groupby("StockCode")["Description"]
        .agg(lambda x: x.value_counts().index[0])
        .to_dict()
    )
    merchandise["ProductName"] = merchandise["StockCode"].map(canonical_names)
    return merchandise


def validate_merchandise_data(df: pd.DataFrame) -> None:
    """Confirm invalid sales did not survive cleaning."""
    assert (df["Quantity"] > 0).all()
    assert (df["UnitPrice"] > 0).all()
    assert not df["InvoiceNo"].str.startswith("C", na=False).any()
    assert df["Revenue"].notna().all()


def build_monthly_performance(df: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        df.groupby("YearMonth")
        .agg(
            Revenue=("Revenue", "sum"),
            Orders=("InvoiceNo", "nunique"),
        )
        .reset_index()
    )
    monthly["YearMonth"] = monthly["YearMonth"].astype(str)
    return monthly


def build_product_performance(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["StockCode", "ProductName"])
        .agg(
            Revenue=("Revenue", "sum"),
            UnitsSold=("Quantity", "sum"),
            Orders=("InvoiceNo", "nunique"),
        )
        .reset_index()
        .sort_values("Revenue", ascending=False)
    )


def build_country_performance(df: pd.DataFrame) -> pd.DataFrame:
    country = (
        df.groupby("Country")
        .agg(
            Revenue=("Revenue", "sum"),
            Orders=("InvoiceNo", "nunique"),
            UnitsSold=("Quantity", "sum"),
            Customers=("CustomerID", "nunique"),
        )
        .reset_index()
    )
    country["AverageOrderValue"] = country["Revenue"] / country["Orders"]
    return country.sort_values("Revenue", ascending=False)


def calculate_sales_kpis(df: pd.DataFrame) -> dict:
    revenue = df["Revenue"].sum()
    orders = df["InvoiceNo"].nunique()
    return {
        "revenue": revenue,
        "orders": orders,
        "units": int(df["Quantity"].sum()),
        "average_order_value": revenue / orders,
    }


def assign_segment(row: pd.Series) -> str:
    """Assign a business-readable segment from RFM scores."""
    r, f, m = row["R_Score"], row["F_Score"], row["M_Score"]

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r <= 2 and f >= 4 and m >= 4:
        return "Can't Lose Them"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r == 5 and f == 1:
        return "Recent One-Time Buyers"
    if r >= 4 and f in (2, 3):
        return "Potential Loyalists"
    if r >= 3 and f >= 4:
        return "Loyal Customers"
    if r <= 2 and f <= 2:
        return "Hibernating"
    return "Needs Attention"


def build_rfm(df: pd.DataFrame) -> pd.DataFrame:
    customer_sales = df[df["CustomerID"].notna()].copy()
    reference_date = customer_sales["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = (
        customer_sales.groupby("CustomerID")
        .agg(
            LastPurchase=("InvoiceDate", "max"),
            Frequency=("InvoiceNo", "nunique"),
            Monetary=("Revenue", "sum"),
        )
        .reset_index()
    )
    rfm["Recency"] = (reference_date - rfm["LastPurchase"]).dt.days

    # Percentile ranks preserve ties instead of arbitrarily splitting customers.
    recency_pct = rfm["Recency"].rank(method="average", pct=True, ascending=True)
    frequency_pct = rfm["Frequency"].rank(method="average", pct=True)
    monetary_pct = rfm["Monetary"].rank(method="average", pct=True)

    rfm["R_Score"] = (6 - np.ceil(recency_pct * 5)).astype(int)
    rfm["F_Score"] = np.ceil(frequency_pct * 5).astype(int)
    rfm["M_Score"] = np.ceil(monetary_pct * 5).astype(int)
    rfm["Segment"] = rfm.apply(assign_segment, axis=1)

    return rfm[
        [
            "CustomerID", "Recency", "Frequency", "Monetary", "LastPurchase",
            "R_Score", "F_Score", "M_Score", "Segment",
        ]
    ]


def build_segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rfm.groupby("Segment")
        .agg(
            Customers=("CustomerID", "count"),
            Revenue=("Monetary", "sum"),
            AvgRevenue=("Monetary", "mean"),
            AvgFrequency=("Frequency", "mean"),
            AvgRecency=("Recency", "mean"),
        )
        .reset_index()
    )
    summary["CustomerShare"] = summary["Customers"] / len(rfm) * 100
    summary["RevenueShare"] = summary["Revenue"] / rfm["Monetary"].sum() * 100
    return summary.sort_values("Revenue", ascending=False)


def calculate_customer_metrics(rfm: pd.DataFrame) -> dict:
    repeat_mask = rfm["Frequency"] > 1
    total_revenue = rfm["Monetary"].sum()
    repeat_revenue = rfm.loc[repeat_mask, "Monetary"].sum()

    return {
        "customers": len(rfm),
        "repeat_customers": int(repeat_mask.sum()),
        "one_time_customers": int((~repeat_mask).sum()),
        "repeat_rate": repeat_mask.mean() * 100,
        "repeat_revenue_share": repeat_revenue / total_revenue * 100,
        "top_100_revenue_share": (
            rfm.nlargest(100, "Monetary")["Monetary"].sum()
            / total_revenue
            * 100
        ),
    }


def export_results(
    merchandise: pd.DataFrame,
    monthly: pd.DataFrame,
    products: pd.DataFrame,
    countries: pd.DataFrame,
    rfm: pd.DataFrame,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    merchandise.to_csv(DATA_DIR / "online_retail_clean.csv", index=False)
    monthly.to_csv(DATA_DIR / "monthly_revenue.csv", index=False)
    products.to_csv(DATA_DIR / "product_performance.csv", index=False)
    countries.to_csv(DATA_DIR / "country_performance.csv", index=False)
    rfm.to_csv(DATA_DIR / "customer_rfm_segments.csv", index=False)

    sql_sales = merchandise.copy()
    sql_sales["YearMonth"] = sql_sales["YearMonth"].astype(str)

    with sqlite3.connect(DATABASE_FILE) as conn:
        sql_sales.to_sql("sales", conn, if_exists="replace", index=False)
        rfm.to_sql("customer_segments", conn, if_exists="replace", index=False)


def print_summary(
    audit: dict,
    merchandise: pd.DataFrame,
    kpis: dict,
    customer_metrics: dict,
    segments: pd.DataFrame,
) -> None:
    uk_share = (
        merchandise.loc[
            merchandise["Country"] == "United Kingdom", "Revenue"
        ].sum()
        / kpis["revenue"]
        * 100
    )
    champions = segments.loc[segments["Segment"] == "Champions"].iloc[0]

    print("\nDATA QUALITY")
    print(f"Raw rows: {audit['rows']:,}")
    print(f"Duplicates identified: {audit['duplicates']:,}")
    print(f"Missing Customer IDs: {audit['missing_customer_ids']:,}")
    print(f"Date range: {audit['first_transaction']} to {audit['last_transaction']}")

    print("\nMERCHANDISE KPIs")
    print(f"Rows: {len(merchandise):,}")
    print(f"Revenue: £{kpis['revenue']:,.2f}")
    print(f"Orders: {kpis['orders']:,}")
    print(f"Units sold: {kpis['units']:,}")
    print(f"Average order value: £{kpis['average_order_value']:,.2f}")
    print(f"UK revenue share: {uk_share:.1f}%")

    print("\nCUSTOMER FINDINGS")
    print(f"Customers: {customer_metrics['customers']:,}")
    print(f"Repeat customer rate: {customer_metrics['repeat_rate']:.1f}%")
    print(
        f"Repeat customer revenue share: "
        f"{customer_metrics['repeat_revenue_share']:.1f}%"
    )
    print(
        f"Top 100 customer revenue share: "
        f"{customer_metrics['top_100_revenue_share']:.1f}%"
    )
    print(
        f"Champions: {int(champions['Customers']):,} customers, "
        f"{champions['RevenueShare']:.1f}% of attributable revenue"
    )

    print(f"\nExports: {DATA_DIR}")
    print(f"SQLite database: {DATABASE_FILE}")


def main() -> None:
    raw = load_data(RAW_FILE)
    audit = audit_data(raw)

    sales = clean_sales_data(raw)
    merchandise = create_merchandise_data(sales)
    print(
    merchandise[
        merchandise["Description"].str.contains(
            "PACKING CHARGE",
            case=False,
            na=False
        )
    ][["StockCode", "Description", "Quantity", "UnitPrice", "Revenue"]]
    .to_string(index=False)
)
    validate_merchandise_data(merchandise)

    monthly = build_monthly_performance(merchandise)
    products = build_product_performance(merchandise)
    countries = build_country_performance(merchandise)
    kpis = calculate_sales_kpis(merchandise)

    rfm = build_rfm(merchandise)
    segments = build_segment_summary(rfm)
    customer_metrics = calculate_customer_metrics(rfm)

    export_results(merchandise, monthly, products, countries, rfm)
    print_summary(audit, merchandise, kpis, customer_metrics, segments)


if __name__ == "__main__":
    main()
