from __future__ import annotations

import argparse
import math
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


TENANT_NAMESPACE = uuid.UUID("f1666936-b8db-4b45-989b-cd378404c3c4")

CATEGORIES = [
    "Épicerie",
    "Boissons",
    "Hygiène",
    "Entretien",
    "Papeterie",
    "Électronique",
]

STORE_LOCATIONS = [
    ("Casablanca", "Casablanca-Settat"),
    ("Rabat", "Rabat-Salé-Kénitra"),
    ("Marrakech", "Marrakech-Safi"),
    ("Agadir", "Souss-Massa"),
    ("Fès", "Fès-Meknès"),
]


@dataclass(frozen=True)
class ProductProfile:
    product_id: str
    tenant_id: str
    supplier_id: str
    sku: str
    product_name: str
    category_name: str
    purchase_price: float
    selling_price: float
    lead_time_days: int
    minimum_order_quantity: int
    package_size: int
    base_daily_demand: float
    annual_amplitude: float
    annual_phase: float
    monthly_trend: float
    demand_variability: float


def deterministic_uuid(value: str) -> str:
    """Return a reproducible UUID from a stable string."""
    return str(uuid.uuid5(TENANT_NAMESPACE, value))


def round_to_package(
    quantity: float,
    package_size: int,
    minimum_order_quantity: int,
) -> int:
    """Round an order quantity to valid packaging constraints."""
    required = max(quantity, minimum_order_quantity)
    return int(math.ceil(required / package_size) * package_size)


def build_reference_data(
    rng: np.random.Generator,
    number_of_products: int,
    number_of_stores: int,
    number_of_suppliers: int,
    created_at: str,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    list[ProductProfile],
]:
    tenant_id = deterministic_uuid("company-stockpilot-demo")

    companies = pd.DataFrame(
        [
            {
                "tenant_id": tenant_id,
                "company_name": "StockPilot Demo Distribution",
                "industry": "Retail and distribution",
                "country": "Morocco",
                "created_at": created_at,
            }
        ]
    )

    store_rows: list[dict] = []

    for index in range(number_of_stores):
        city, region = STORE_LOCATIONS[index % len(STORE_LOCATIONS)]
        store_code = f"STORE-{index + 1:03d}"

        store_rows.append(
            {
                "store_id": deterministic_uuid(f"store-{store_code}"),
                "tenant_id": tenant_id,
                "store_code": store_code,
                "store_name": f"Magasin {city}",
                "city": city,
                "region": region,
                "active": True,
                "created_at": created_at,
            }
        )

    stores = pd.DataFrame(store_rows)

    supplier_rows: list[dict] = []

    for index in range(number_of_suppliers):
        supplier_code = f"SUP-{index + 1:03d}"

        supplier_rows.append(
            {
                "supplier_id": deterministic_uuid(
                    f"supplier-{supplier_code}"
                ),
                "tenant_id": tenant_id,
                "supplier_code": supplier_code,
                "supplier_name": f"Fournisseur {index + 1:02d}",
                "average_lead_time_days": int(
                    rng.integers(3, 18)
                ),
                "minimum_order_value": float(
                    rng.choice([300, 500, 750, 1000, 1500])
                ),
                "active": True,
                "created_at": created_at,
            }
        )

    suppliers = pd.DataFrame(supplier_rows)

    product_rows: list[dict] = []
    product_profiles: list[ProductProfile] = []

    package_choices = np.array([1, 5, 6, 10, 12, 20, 24])

    for index in range(number_of_products):
        sku = f"SKU-{index + 1:05d}"
        category = CATEGORIES[index % len(CATEGORIES)]
        supplier = supplier_rows[index % number_of_suppliers]

        purchase_price = round(
            float(rng.lognormal(mean=3.4, sigma=0.75)),
            2,
        )
        margin_rate = float(rng.uniform(0.18, 0.55))
        selling_price = round(
            purchase_price / (1 - margin_rate),
            2,
        )

        package_size = int(rng.choice(package_choices))
        minimum_order_quantity = package_size * int(
            rng.integers(1, 5)
        )

        lead_time_days = int(
            max(
                1,
                supplier["average_lead_time_days"]
                + rng.integers(-2, 4),
            )
        )

        # A log-normal distribution produces many medium sellers,
        # a few slow sellers and a few very popular products.
        base_daily_demand = float(
            np.clip(
                rng.lognormal(mean=1.3, sigma=1.0),
                0.08,
                40,
            )
        )

        annual_amplitude = float(rng.uniform(0.0, 0.45))
        annual_phase = float(rng.uniform(0, 2 * np.pi))
        monthly_trend = float(rng.uniform(-0.012, 0.025))
        demand_variability = float(rng.uniform(0.12, 0.45))

        product_id = deterministic_uuid(f"product-{sku}")
        product_name = f"{category} - Produit {index + 1:04d}"

        product_rows.append(
            {
                "product_id": product_id,
                "tenant_id": tenant_id,
                "supplier_id": supplier["supplier_id"],
                "sku": sku,
                "product_name": product_name,
                "category_name": category,
                "purchase_price": purchase_price,
                "selling_price": selling_price,
                "lead_time_days": lead_time_days,
                "minimum_order_quantity": minimum_order_quantity,
                "package_size": package_size,
                "active": True,
                "created_at": created_at,
            }
        )

        product_profiles.append(
            ProductProfile(
                product_id=product_id,
                tenant_id=tenant_id,
                supplier_id=supplier["supplier_id"],
                sku=sku,
                product_name=product_name,
                category_name=category,
                purchase_price=purchase_price,
                selling_price=selling_price,
                lead_time_days=lead_time_days,
                minimum_order_quantity=minimum_order_quantity,
                package_size=package_size,
                base_daily_demand=base_daily_demand,
                annual_amplitude=annual_amplitude,
                annual_phase=annual_phase,
                monthly_trend=monthly_trend,
                demand_variability=demand_variability,
            )
        )

    products = pd.DataFrame(product_rows)

    return (
        companies,
        stores,
        suppliers,
        products,
        product_profiles,
    )


def build_promotions(
    rng: np.random.Generator,
    tenant_id: str,
    stores: pd.DataFrame,
    products: list[ProductProfile],
    dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, dict[tuple[str, str, pd.Timestamp], float]]:
    promotion_rows: list[dict] = []
    promotion_lookup: dict[
        tuple[str, str, pd.Timestamp],
        float,
    ] = {}

    maximum_start_offset = max(1, len(dates) - 15)
    promotion_number = 1

    for store in stores.itertuples(index=False):
        for product in products:
            # Not every product is frequently promoted.
            if rng.random() > 0.55:
                continue

            number_of_promotions = int(
                rng.integers(1, 5)
            )

            for _ in range(number_of_promotions):
                start_offset = int(
                    rng.integers(0, maximum_start_offset)
                )
                duration_days = int(rng.integers(5, 15))
                discount = float(
                    rng.choice([5, 10, 15, 20, 25])
                )

                start_date = dates[start_offset]
                end_date = min(
                    start_date
                    + pd.Timedelta(days=duration_days - 1),
                    dates[-1],
                )

                promotion_id = deterministic_uuid(
                    f"promotion-{promotion_number}"
                )

                promotion_rows.append(
                    {
                        "promotion_id": promotion_id,
                        "tenant_id": tenant_id,
                        "product_id": product.product_id,
                        "store_id": store.store_id,
                        "start_date": start_date.date().isoformat(),
                        "end_date": end_date.date().isoformat(),
                        "discount_percentage": discount,
                    }
                )

                for date in pd.date_range(
                    start_date,
                    end_date,
                    freq="D",
                ):
                    promotion_lookup[
                        (
                            store.store_id,
                            product.product_id,
                            date.normalize(),
                        )
                    ] = discount

                promotion_number += 1

    return pd.DataFrame(promotion_rows), promotion_lookup


def simulate_sales_inventory_and_orders(
    rng: np.random.Generator,
    stores: pd.DataFrame,
    products: list[ProductProfile],
    dates: pd.DatetimeIndex,
    promotion_lookup: dict[
        tuple[str, str, pd.Timestamp],
        float,
    ],
    imported_at: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sales_rows: list[dict] = []
    inventory_rows: list[dict] = []
    purchase_order_rows: list[dict] = []

    end_date = dates[-1]
    order_counter = 1

    for store_index, store in enumerate(
        stores.itertuples(index=False)
    ):
        store_factor = 1.0 + (store_index * 0.12)

        for product in products:
            expected_daily_demand = (
                product.base_daily_demand * store_factor
            )

            initial_stock = max(
                product.minimum_order_quantity,
                round_to_package(
                    expected_daily_demand
                    * rng.uniform(25, 55),
                    product.package_size,
                    product.minimum_order_quantity,
                ),
            )

            stock_on_hand = int(initial_stock)
            outstanding_orders: list[dict] = []

            for day_index, date in enumerate(dates):
                # Receive orders whose actual arrival date is today.
                arrivals = [
                    order
                    for order in outstanding_orders
                    if order["arrival_date"] <= date
                ]

                for order in arrivals:
                    stock_on_hand += order["quantity"]

                outstanding_orders = [
                    order
                    for order in outstanding_orders
                    if order["arrival_date"] > date
                ]

                weekday_factor = {
                    0: 0.92,
                    1: 0.98,
                    2: 1.00,
                    3: 1.04,
                    4: 1.14,
                    5: 1.28,
                    6: 0.74,
                }[date.dayofweek]

                annual_factor = 1 + (
                    product.annual_amplitude
                    * math.sin(
                        (2 * math.pi * date.dayofyear / 365.25)
                        + product.annual_phase
                    )
                )

                elapsed_months = day_index / 30.44
                trend_factor = max(
                    0.55,
                    1
                    + (
                        product.monthly_trend
                        * elapsed_months
                    ),
                )

                discount = promotion_lookup.get(
                    (
                        store.store_id,
                        product.product_id,
                        date.normalize(),
                    ),
                    0.0,
                )

                promotion_factor = (
                    1.0 + (discount / 100) * 2.2
                    if discount > 0
                    else 1.0
                )

                multiplicative_noise = float(
                    rng.lognormal(
                        mean=0,
                        sigma=product.demand_variability,
                    )
                )

                expected_demand = (
                    expected_daily_demand
                    * weekday_factor
                    * annual_factor
                    * trend_factor
                    * promotion_factor
                    * multiplicative_noise
                )

                expected_demand = max(0.02, expected_demand)
                requested_quantity = int(
                    rng.poisson(expected_demand)
                )

                sold_quantity = min(
                    requested_quantity,
                    stock_on_hand,
                )

                unmet_demand = max(
                    0,
                    requested_quantity - sold_quantity,
                )

                stock_on_hand -= sold_quantity

                # A minority of unmet retail demand becomes backorders.
                backorders = int(
                    round(unmet_demand * rng.uniform(0.05, 0.25))
                )

                if sold_quantity > 0:
                    sale_reference = (
                        f"SALE-{date:%Y%m%d}-"
                        f"{store.store_code}-{product.sku}"
                    )

                    total_amount = round(
                        sold_quantity
                        * product.selling_price
                        * (1 - discount / 100),
                        2,
                    )

                    sales_rows.append(
                        {
                            "sale_id": deterministic_uuid(
                                sale_reference
                            ),
                            "tenant_id": product.tenant_id,
                            "sale_reference": sale_reference,
                            "sale_date": date.date().isoformat(),
                            "store_id": store.store_id,
                            "product_id": product.product_id,
                            "quantity": sold_quantity,
                            "unit_price": product.selling_price,
                            "discount_percentage": discount,
                            "total_amount": total_amount,
                            "imported_at": imported_at,
                        }
                    )

                quantity_on_order = sum(
                    order["quantity"]
                    for order in outstanding_orders
                )

                average_demand = max(
                    0.1,
                    expected_daily_demand,
                )

                demand_during_lead_time = (
                    average_demand
                    * product.lead_time_days
                )

                safety_stock = (
                    1.65
                    * math.sqrt(product.lead_time_days)
                    * max(1.0, average_demand * 0.35)
                )

                reorder_point = (
                    demand_during_lead_time + safety_stock
                )

                inventory_position = (
                    stock_on_hand
                    + quantity_on_order
                    - backorders
                )

                target_stock = (
                    average_demand
                    * (product.lead_time_days + 21)
                    + safety_stock
                )

                if inventory_position <= reorder_point:
                    raw_order_quantity = max(
                        0,
                        target_stock - inventory_position,
                    )

                    ordered_quantity = round_to_package(
                        raw_order_quantity,
                        product.package_size,
                        product.minimum_order_quantity,
                    )

                    expected_delivery_date = (
                        date
                        + pd.Timedelta(
                            days=product.lead_time_days
                        )
                    )

                    supplier_delay = int(
                        rng.choice(
                            [-1, 0, 0, 0, 1, 1, 2, 3]
                        )
                    )

                    actual_arrival_date = max(
                        date + pd.Timedelta(days=1),
                        expected_delivery_date
                        + pd.Timedelta(days=supplier_delay),
                    )

                    purchase_order_id = deterministic_uuid(
                        f"purchase-order-{order_counter}"
                    )

                    order_status = (
                        "received"
                        if actual_arrival_date <= end_date
                        else "open"
                    )

                    purchase_order_rows.append(
                        {
                            "purchase_order_id":
                                purchase_order_id,
                            "tenant_id": product.tenant_id,
                            "supplier_id": product.supplier_id,
                            "product_id": product.product_id,
                            "store_id": store.store_id,
                            "order_date":
                                date.date().isoformat(),
                            "expected_delivery_date":
                                expected_delivery_date
                                .date()
                                .isoformat(),
                            "actual_delivery_date":
                                (
                                    actual_arrival_date
                                    .date()
                                    .isoformat()
                                    if order_status == "received"
                                    else None
                                ),
                            "ordered_quantity":
                                ordered_quantity,
                            "received_quantity":
                                (
                                    ordered_quantity
                                    if order_status == "received"
                                    else 0
                                ),
                            "status": order_status,
                        }
                    )

                    outstanding_orders.append(
                        {
                            "arrival_date":
                                actual_arrival_date,
                            "quantity":
                                ordered_quantity,
                        }
                    )

                    quantity_on_order += ordered_quantity
                    order_counter += 1

                inventory_reference = (
                    f"inventory-{date:%Y%m%d}-"
                    f"{store.store_code}-{product.sku}"
                )

                inventory_rows.append(
                    {
                        "inventory_id": deterministic_uuid(
                            inventory_reference
                        ),
                        "tenant_id": product.tenant_id,
                        "inventory_date":
                            date.date().isoformat(),
                        "store_id": store.store_id,
                        "product_id": product.product_id,
                        "stock_on_hand": stock_on_hand,
                        "quantity_on_order":
                            quantity_on_order,
                        "backorders": backorders,
                        "imported_at": imported_at,
                    }
                )

    return (
        pd.DataFrame(sales_rows),
        pd.DataFrame(inventory_rows),
        pd.DataFrame(purchase_order_rows),
    )


def create_invalid_quality_sample(
    sales: pd.DataFrame,
    output_directory: Path,
) -> None:
    """Create isolated invalid records for future ETL tests."""
    if sales.empty:
        return

    sample = sales.head(4).copy()

    sample.loc[sample.index[0], "quantity"] = -5

    if len(sample) > 1:
        sample.loc[sample.index[1], "sale_date"] = "invalid-date"

    if len(sample) > 2:
        sample.loc[
            sample.index[2],
            "product_id",
        ] = "00000000-0000-0000-0000-000000000000"

    if len(sample) > 3:
        sample.loc[
            sample.index[3],
            "sale_reference",
        ] = sample.iloc[0]["sale_reference"]

    sample.to_csv(
        output_directory / "sales_invalid.csv",
        index=False,
        encoding="utf-8",
    )


def save_dataframe(
    dataframe: pd.DataFrame,
    output_path: Path,
) -> None:
    dataframe.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
    )

    print(
        f"{output_path.name:<24}"
        f"{len(dataframe):>12,} rows"
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate reproducible synthetic retail data "
            "for StockPilot AI."
        )
    )

    parser.add_argument(
        "--start-date",
        default="2024-01-01",
        help="Simulation start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Number of simulated calendar days.",
    )
    parser.add_argument(
        "--products",
        type=int,
        default=120,
        help="Number of products.",
    )
    parser.add_argument(
        "--stores",
        type=int,
        default=2,
        help="Number of stores.",
    )
    parser.add_argument(
        "--suppliers",
        type=int,
        default=8,
        help="Number of suppliers.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--output",
        default="data/generated",
        help="Directory for valid generated CSV files.",
    )
    parser.add_argument(
        "--quality-output",
        default="data/quality_samples",
        help="Directory for intentionally invalid CSV files.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.days < 30:
        raise ValueError("--days must be at least 30.")

    if args.products < 1:
        raise ValueError("--products must be positive.")

    if args.stores < 1:
        raise ValueError("--stores must be positive.")

    if args.suppliers < 1:
        raise ValueError("--suppliers must be positive.")

    output_directory = Path(args.output)
    quality_directory = Path(args.quality_output)

    output_directory.mkdir(parents=True, exist_ok=True)
    quality_directory.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)

    dates = pd.date_range(
        start=args.start_date,
        periods=args.days,
        freq="D",
    )

    created_at = (
        f"{dates[0].date().isoformat()}T00:00:00+00:00"
    )
    imported_at = (
        f"{dates[-1].date().isoformat()}T23:59:59+00:00"
    )

    (
        companies,
        stores,
        suppliers,
        products,
        product_profiles,
    ) = build_reference_data(
        rng=rng,
        number_of_products=args.products,
        number_of_stores=args.stores,
        number_of_suppliers=args.suppliers,
        created_at=created_at,
    )

    tenant_id = companies.iloc[0]["tenant_id"]

    promotions, promotion_lookup = build_promotions(
        rng=rng,
        tenant_id=tenant_id,
        stores=stores,
        products=product_profiles,
        dates=dates,
    )

    (
        sales,
        inventory,
        purchase_orders,
    ) = simulate_sales_inventory_and_orders(
        rng=rng,
        stores=stores,
        products=product_profiles,
        dates=dates,
        promotion_lookup=promotion_lookup,
        imported_at=imported_at,
    )

    print("\nGenerated StockPilot AI dataset")
    print("-" * 42)

    save_dataframe(
        companies,
        output_directory / "companies.csv",
    )
    save_dataframe(
        stores,
        output_directory / "stores.csv",
    )
    save_dataframe(
        suppliers,
        output_directory / "suppliers.csv",
    )
    save_dataframe(
        products,
        output_directory / "products.csv",
    )
    save_dataframe(
        promotions,
        output_directory / "promotions.csv",
    )
    save_dataframe(
        purchase_orders,
        output_directory / "purchase_orders.csv",
    )
    save_dataframe(
        sales,
        output_directory / "sales.csv",
    )
    save_dataframe(
        inventory,
        output_directory / "inventory.csv",
    )

    create_invalid_quality_sample(
        sales=sales,
        output_directory=quality_directory,
    )

    print("-" * 42)
    print(
        f"Period: {dates[0].date()} to {dates[-1].date()}"
    )
    print(f"Random seed: {args.seed}")
    print(f"Valid output: {output_directory.resolve()}")
    print(
        f"Quality samples: {quality_directory.resolve()}"
    )


if __name__ == "__main__":
    main()