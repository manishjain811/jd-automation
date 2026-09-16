import os
import time
from collections import defaultdict

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

ENV = "prod"
INPUT_FILE = "generated/asset_import.csv"
PRODUCT_ASSET_ATTRIBUTE = "JD_AssetLink"
FLUENT_IMAGE_ATTRIBUTE = "gmg_fluentImage"
S3_BASE_URL = "https://omniversemedia.s3.eu-central-1.amazonaws.com/"

TOKEN_REFRESH_SECONDS = 50 * 60
MAX_RETRIES = 5
RETRY_BACKOFF = 5
REQUEST_TIMEOUT = 60

BASE_URL = os.getenv("AKENEO_BASE_URL", "https://gmg.cloud.akeneo.com").rstrip("/")
USERNAME = os.getenv("AKENEO_USERNAME")
PASSWORD = os.getenv("AKENEO_PASSWORD")
CLIENT_SECRET = os.getenv("AKENEO_BASIC_AUTH")

if not USERNAME:
    raise Exception("AKENEO_USERNAME is not configured")
if not PASSWORD:
    raise Exception("AKENEO_PASSWORD is not configured")
if not CLIENT_SECRET:
    raise Exception("AKENEO_BASIC_AUTH is not configured")

session = requests.Session()

retry_strategy = Retry(
    total=3,
    connect=3,
    read=3,
    status=3,
    backoff_factor=2,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST", "PATCH"],
    raise_on_status=False
)

adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=10,
    pool_maxsize=10
)

session.mount("https://", adapter)
session.mount("http://", adapter)

token_created_at = 0


def get_token():
    global token_created_at

    print("🔐 Authenticating with Akeneo...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.post(
                f"{BASE_URL}/api/oauth/v1/token",
                json={
                    "username": USERNAME,
                    "password": PASSWORD,
                    "grant_type": "password"
                },
                headers={
                    "Authorization": f"Basic {CLIENT_SECRET}",
                    "Content-Type": "application/json"
                },
                timeout=REQUEST_TIMEOUT
            )

            if r.status_code != 200:
                print(f"❌ Authentication failed: HTTP {r.status_code}")
                print(f"Response: {r.text}")
                r.raise_for_status()

            data = r.json()
            token_created_at = time.time()

            print("✅ Authentication successful")
            return data["access_token"], data.get("refresh_token")

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"⚠️ Authentication network error (attempt {attempt}/{MAX_RETRIES}): {e}")

            if attempt < MAX_RETRIES:
                wait_time = RETRY_BACKOFF * attempt
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise

    raise RuntimeError("Unable to authenticate with Akeneo.")


def ensure_valid_token(token, refresh_token_value):
    global token_created_at

    token_age = time.time() - token_created_at

    if token_age >= TOKEN_REFRESH_SECONDS:
        print(f"\n⏰ Access token is approximately {int(token_age / 60)} minutes old.")
        print("🔄 Proactively refreshing token...")
        token, refresh_token_value = refresh_access_token(refresh_token_value)

    return token, refresh_token_value


def refresh_access_token(refresh_token_value):
    global token_created_at

    if not refresh_token_value:
        print("⚠️ No refresh token available.")
        print("🔐 Performing full authentication...")
        return get_token()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print("🔄 Refreshing Akeneo access token...")

            r = session.post(
                f"{BASE_URL}/api/oauth/v1/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value
                },
                headers={
                    "Authorization": f"Basic {CLIENT_SECRET}",
                    "Content-Type": "application/json"
                },
                timeout=REQUEST_TIMEOUT
            )

            if r.status_code in (400, 401):
                print("⚠️ Refresh token is invalid/expired.")
                print("🔐 Performing full Akeneo authentication...")
                return get_token()

            r.raise_for_status()

            data = r.json()
            token_created_at = time.time()

            new_access_token = data["access_token"]
            new_refresh_token = data.get("refresh_token", refresh_token_value)

            print("✅ Access token refreshed")
            return new_access_token, new_refresh_token

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"⚠️ Token refresh network error (attempt {attempt}/{MAX_RETRIES}): {e}")

            if attempt < MAX_RETRIES:
                wait_time = RETRY_BACKOFF * attempt
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise

    raise RuntimeError("Unable to refresh Akeneo token.")


def get_product(token, refresh_token_value, sku):
    url = f"{BASE_URL}/api/rest/v1/products/{sku}"
    token, refresh_token_value = ensure_valid_token(token, refresh_token_value)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT
            )

            if r.status_code == 404:
                return None, token, refresh_token_value

            if r.status_code == 401:
                print(f"🔄 Access token expired while fetching product {sku}")
                token, refresh_token_value = refresh_access_token(refresh_token_value)

                r = session.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=REQUEST_TIMEOUT
                )

                if r.status_code == 404:
                    return None, token, refresh_token_value

                if r.status_code == 401:
                    print(f"❌ Still unauthorized after token refresh: {sku}")
                    r.raise_for_status()

            if r.status_code in (502, 503, 504):
                print(f"⚠️ Akeneo returned HTTP {r.status_code} for {sku} (attempt {attempt}/{MAX_RETRIES})")

                if attempt < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF * attempt
                    print(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

            r.raise_for_status()
            return r.json(), token, refresh_token_value

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"⚠️ Network error fetching {sku} (attempt {attempt}/{MAX_RETRIES})")
            print(f"   {e}")

            if attempt < MAX_RETRIES:
                wait_time = RETRY_BACKOFF * attempt
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"❌ Failed after {MAX_RETRIES} attempts: {sku}")
                raise

    raise RuntimeError(f"Unable to fetch product: {sku}")


def get_product_model(token, refresh_token_value, model_code):
    url = f"{BASE_URL}/api/rest/v1/product-models/{model_code}"
    token, refresh_token_value = ensure_valid_token(token, refresh_token_value)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=REQUEST_TIMEOUT
            )

            if r.status_code == 404:
                return None, token, refresh_token_value

            if r.status_code == 401:
                print(f"🔄 Access token expired while fetching product model {model_code}")
                token, refresh_token_value = refresh_access_token(refresh_token_value)

                r = session.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=REQUEST_TIMEOUT
                )

                if r.status_code == 404:
                    return None, token, refresh_token_value

            if r.status_code in (502, 503, 504):
                print(f"⚠️ Akeneo returned HTTP {r.status_code} for model {model_code} (attempt {attempt}/{MAX_RETRIES})")

                if attempt < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF * attempt
                    print(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

            r.raise_for_status()
            return r.json(), token, refresh_token_value

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"⚠️ Network error fetching model {model_code} (attempt {attempt}/{MAX_RETRIES})")
            print(f"   {e}")

            if attempt < MAX_RETRIES:
                wait_time = RETRY_BACKOFF * attempt
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise

    raise RuntimeError(f"Unable to fetch product model: {model_code}")


def update_product_model(token, refresh_token_value, model_code, asset_codes, fluent_image_url):
    payload = {
        "values": {
            PRODUCT_ASSET_ATTRIBUTE: [
                {
                    "locale": None,
                    "scope": None,
                    "data": asset_codes
                }
            ],
            FLUENT_IMAGE_ATTRIBUTE: [
                {
                    "locale": None,
                    "scope": "jd",
                    "data": fluent_image_url
                }
            ]
        }
    }

    url = f"{BASE_URL}/api/rest/v1/product-models/{model_code}"
    token, refresh_token_value = ensure_valid_token(token, refresh_token_value)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.patch(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            if r.status_code == 401:
                print(f"🔄 Access token expired while updating product model {model_code}")
                token, refresh_token_value = refresh_access_token(refresh_token_value)

                r = session.patch(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )

            if r.status_code in (502, 503, 504):
                print(f"⚠️ Akeneo returned HTTP {r.status_code} while updating {model_code} (attempt {attempt}/{MAX_RETRIES})")

                if attempt < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF * attempt
                    print(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

            if r.status_code in (200, 201, 204):
                print(f"✅ PATCH successful: HTTP {r.status_code}")

                verify_product_model, token, refresh_token_value = get_product_model(
                    token,
                    refresh_token_value,
                    model_code
                )

                if verify_product_model:
                    fluent_values = verify_product_model.get("values", {}).get(
                        FLUENT_IMAGE_ATTRIBUTE,
                        []
                    )

                    print("\n========== FLUENT VALUE AFTER PATCH ==========")
                    print(f"Model: {model_code}")
                    print(f"gmg_fluentImage: {fluent_values}")
                    print("==============================================\n")

                return token, refresh_token_value

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"⚠️ Network error updating model {model_code} (attempt {attempt}/{MAX_RETRIES})")
            print(f"   {e}")

            if attempt < MAX_RETRIES:
                wait_time = RETRY_BACKOFF * attempt
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise

    raise RuntimeError(f"Unable to update product model: {model_code}")


def main():
    print(f"📄 Reading CSV: {INPUT_FILE}\n")

    df = pd.read_csv(INPUT_FILE, sep=";")

    print(f"📊 Total CSV rows: {len(df)}\n")

    token, refresh_token_value = get_token()

    model_assets = defaultdict(list)
    model_fluent_image = {}

    for row_number, row in enumerate(df.itertuples(index=False), start=1):
        try:
            asset_code = str(row.code).strip()
        except AttributeError:
            print(f"⚠️ Row {row_number}: 'code' column not found")
            continue

        try:
            parts = asset_code.split("_")
            variant_sku = parts[1]
            image_index = parts[2]
        except (IndexError, AttributeError):
            print(f"⚠️ Invalid asset code format: {asset_code}")
            continue

        product, token, refresh_token_value = get_product(
            token,
            refresh_token_value,
            variant_sku
        )

        if not product:
            print(f"⚠️ Variant not found: {variant_sku}")
            continue

        model_code = product.get("parent")

        if not model_code:
            print(f"⚠️ Variant has no parent: {variant_sku}")
            continue

        model_assets[model_code].append(asset_code)

        if model_code not in model_fluent_image:
            model_fluent_image[model_code] = (
                f"{S3_BASE_URL}"
                f"jd/images/"
                f"{variant_sku}/"
                f"{variant_sku}_{image_index}.jpg"
            )

        print(f"   ➕ Queued asset {asset_code} for model {model_code}")

        if row_number % 500 == 0:
            print(f"\n📊 Progress: {row_number}/{len(df)} rows processed\n")

    print("\n=====================================================")
    print("🚀 Starting product model updates")
    print("=====================================================\n")

    for model_code, asset_codes in model_assets.items():
        asset_codes = sorted(set(asset_codes))
        fluent_url = model_fluent_image.get(model_code)

        print(f"\n➡️ Updating product model: {model_code}")
        print(f"   🖼 Fluent image: {fluent_url}")
        print(f"   📦 Assets: {len(asset_codes)}")

        token, refresh_token_value = update_product_model(
            token,
            refresh_token_value,
            model_code,
            asset_codes,
            fluent_url
        )

        print(f"   ✅ Linked {len(asset_codes)} assets")

    print("\n=====================================================")
    print("🎉 DONE")
    print("Assets linked + gmg_fluentImage updated")
    print("=====================================================")


if __name__ == "__main__":
    main()