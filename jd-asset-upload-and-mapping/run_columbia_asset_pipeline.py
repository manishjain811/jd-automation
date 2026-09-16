import csv
import requests
import pandas as pd
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import openpyxl

# =====================================================
# CONFIG
# =====================================================
INPUT_XLSX = "input/images.xlsx"
OUTPUT_CSV = "generated/asset_import.csv"

ASSET_FAMILY = "JDphotos"

S3_BUCKET_URL = "https://omniversemedia.s3.amazonaws.com/"
S3_PREFIX = "jd/images"

MAX_IMAGES_PER_VARIANT = 20

CONNECT_TIMEOUT = 2   # seconds
READ_TIMEOUT = 2      # seconds

# =====================================================
# SAFE SESSION (NO HANGS)
# =====================================================
def create_session():
    session = requests.Session()

    retry = Retry(
        total=0,
        connect=0,
        read=0,
        redirect=0,
        status=0
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=5,
        pool_maxsize=5
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


SESSION = create_session()

# =====================================================
# S3 CHECK (HARD SAFE)
# =====================================================
def s3_image_exists(url):
    try:
        r = SESSION.get(
            url,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            allow_redirects=True
        )
        return r.status_code == 200
    except BaseException:
        return False

# =====================================================
# CSV GENERATION
# =====================================================
def generate_csv():
    df = pd.read_excel(
        INPUT_XLSX,
        dtype={"VARIANT_SKU": str, "PRODUCT_MODEL": str}
    )

    required_cols = {"PRODUCT_MODEL", "VARIANT_SKU"}
    if not required_cols.issubset(df.columns):
        raise Exception(
            f"Excel must contain columns: {', '.join(required_cols)}"
        )

    # Ensure STATUS column exists
    if "STATUS" not in df.columns:
        df["STATUS"] = ""

    rows = []

    for idx_row, row in df.iterrows():
        variant_sku = str(row["VARIANT_SKU"]).strip()
        found_any = False

        print(f"clsChecking S3 images for variant: {variant_sku}")

        for idx in range(1, MAX_IMAGES_PER_VARIANT + 1):
            image_url = (
                f"{S3_BUCKET_URL}{S3_PREFIX}/"
                f"{variant_sku}/{variant_sku}_{idx}.jpg"
            )

            if not s3_image_exists(image_url):
                print(f"   ⏭ Missing image, skipping index {idx}")
                continue

            found_any = True
            df.at[idx_row, "STATUS"] = "Done"

            asset_code = f"JD_{variant_sku}_{idx}"
            s3_path = image_url.replace(S3_BUCKET_URL, "")

            rows.append({
                "assetFamilyIdentifier": ASSET_FAMILY,
                "code": asset_code,
                "s3link": s3_path
            })

            print(
                f"   ✅ Added asset | "
                f"code={asset_code} | "
                f"path={s3_path}"
            )

        if not found_any:
            print(f"⚠️ No images found in S3 for variant {variant_sku}")

    if not rows:
        raise Exception("❌ No valid S3 images found for any variant")

    output_path = Path(OUTPUT_CSV)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "assetFamilyIdentifier",
                "code",
                "s3link"
            ],
            delimiter=";"
        )
        writer.writeheader()
        writer.writerows(rows)

    # Save updated Excel with STATUS column
    df.to_excel(INPUT_XLSX, index=False)

    print(f"\n🎉 CSV generation completed")
    print(f"📄 File saved to: {OUTPUT_CSV}")
    print(f"📝 Excel updated with STATUS = Done")
    print("➡ Import this file in Akeneo → Asset Import job")

# =====================================================
if __name__ == "__main__":
    generate_csv()
