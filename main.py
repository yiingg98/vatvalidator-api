from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import re
from typing import Optional, List
from datetime import datetime

app = FastAPI(
    title="VATGuard API",
    description="Validate EU VAT numbers using the official VIES system. Check format, existence, and get company details.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# EU VAT number format patterns per country
VAT_PATTERNS = {
    "AT": r"^ATU\d{8}$",
    "BE": r"^BE0\d{9}$",
    "BG": r"^BG\d{9,10}$",
    "CY": r"^CY\d{8}[A-Z]$",
    "CZ": r"^CZ\d{8,10}$",
    "DE": r"^DE\d{9}$",
    "DK": r"^DK\d{8}$",
    "EE": r"^EE\d{9}$",
    "EL": r"^EL\d{9}$",
    "ES": r"^ES[A-Z0-9]\d{7}[A-Z0-9]$",
    "FI": r"^FI\d{8}$",
    "FR": r"^FR[A-Z0-9]{2}\d{9}$",
    "HR": r"^HR\d{11}$",
    "HU": r"^HU\d{8}$",
    "IE": r"^IE\d[A-Z0-9+*]\d{5}[A-Z]{1,2}$",
    "IT": r"^IT\d{11}$",
    "LT": r"^LT(\d{9}|\d{12})$",
    "LU": r"^LU\d{8}$",
    "LV": r"^LV\d{11}$",
    "MT": r"^MT\d{8}$",
    "NL": r"^NL\d{9}B\d{2}$",
    "PL": r"^PL\d{10}$",
    "PT": r"^PT\d{9}$",
    "RO": r"^RO\d{2,10}$",
    "SE": r"^SE\d{12}$",
    "SI": r"^SI\d{8}$",
    "SK": r"^SK\d{10}$",
    "XI": r"^XI(\d{9}|\d{12}|GD\d{3}|HA\d{3})$",  # Northern Ireland
}

COUNTRY_NAMES = {
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus",
    "CZ": "Czech Republic", "DE": "Germany", "DK": "Denmark", "EE": "Estonia",
    "EL": "Greece", "ES": "Spain", "FI": "Finland", "FR": "France",
    "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta",
    "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
    "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia", "XI": "Northern Ireland"
}

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country_code}/vat/{vat_number}"
VIES_FALLBACK_URL = "https://viesapi.eu/api/search/vat/{country_code}{vat_number}"


def clean_vat(vat: str) -> str:
    return vat.strip().upper().replace(" ", "").replace("-", "").replace(".", "")


def extract_country_code(vat: str) -> Optional[str]:
    if len(vat) >= 2:
        return vat[:2].upper()
    return None


def validate_format(vat: str) -> dict:
    country_code = extract_country_code(vat)
    if not country_code or country_code not in VAT_PATTERNS:
        return {
            "valid_format": False,
            "country_code": country_code,
            "country": None,
            "error": f"Unknown or unsupported country code: {country_code}"
        }

    pattern = VAT_PATTERNS[country_code]
    is_valid = bool(re.match(pattern, vat))

    return {
        "valid_format": is_valid,
        "country_code": country_code,
        "country": COUNTRY_NAMES.get(country_code),
        "error": None if is_valid else f"VAT number format invalid for {COUNTRY_NAMES.get(country_code, country_code)}"
    }


async def check_vies(country_code: str, vat_number: str) -> dict:
    # Strip country code from vat number for VIES API
    number_only = vat_number[len(country_code):]
    url = VIES_URL.format(country_code=country_code, vat_number=number_only)

    default_error = {
        "vies_valid": None,
        "company_name": None,
        "company_address": None,
        "request_date": None,
        "vies_available": False,
        "error": "VIES service unavailable — format check only"
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url)
            if r.status_code == 200:
                try:
                    data = r.json()
                    return {
                        "vies_valid": data.get("isValid", False),
                        "company_name": data.get("name", "").strip() or None,
                        "company_address": data.get("address", "").strip() or None,
                        "request_date": data.get("requestDate"),
                        "vies_available": True,
                        "error": None
                    }
                except Exception:
                    return default_error
            elif r.status_code == 404:
                return {
                    "vies_valid": False,
                    "company_name": None,
                    "company_address": None,
                    "request_date": None,
                    "vies_available": True,
                    "error": "VAT number not found in VIES database"
                }
            else:
                return {
                    "vies_valid": None,
                    "company_name": None,
                    "company_address": None,
                    "request_date": None,
                    "vies_available": False,
                    "error": f"VIES service returned status {r.status_code}"
                }
        except httpx.TimeoutException:
            return {
                "vies_valid": None,
                "company_name": None,
                "company_address": None,
                "request_date": None,
                "vies_available": False,
                "error": "VIES service timed out — try again"
            }
        except Exception:
            return {
                "vies_valid": None,
                "company_name": None,
                "company_address": None,
                "request_date": None,
                "vies_available": False,
                "error": "Could not reach VIES service"
            }


@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {
        "name": "VATGuard API",
        "version": "1.0.0",
        "status": "live",
        "endpoints": [
            "/vat/validate",
            "/vat/format-check",
            "/vat/bulk-validate",
            "/vat/countries"
        ],
        "docs": "/docs"
    }


@app.get("/vat/validate")
async def validate_vat(
    vat: str = Query(..., description="EU VAT number to validate, e.g. DE123456789"),
    check_vies: bool = Query(True, description="Also verify against the official EU VIES database (recommended)")
):
    """
    Full VAT number validation. Checks format and optionally verifies
    against the official EU VIES database. Returns company name and address if available.
    """
    vat = clean_vat(vat)
    format_result = validate_format(vat)

    result = {
        "vat_number": vat,
        "country_code": format_result["country_code"],
        "country": format_result["country"],
        "format_valid": format_result["valid_format"],
        "format_error": format_result["error"],
        "vies_checked": False,
        "vies_valid": None,
        "company_name": None,
        "company_address": None,
        "is_valid": format_result["valid_format"],
        "checked_at": datetime.utcnow().isoformat()
    }

    if format_result["valid_format"] and check_vies:
        vies_result = await check_vies(format_result["country_code"], vat)
        result["vies_checked"] = True
        result["vies_valid"] = vies_result["vies_valid"]
        result["company_name"] = vies_result["company_name"]
        result["company_address"] = vies_result["company_address"]
        result["vies_available"] = vies_result["vies_available"]
        result["vies_error"] = vies_result["error"]
        result["is_valid"] = format_result["valid_format"] and (
            vies_result["vies_valid"] if vies_result["vies_valid"] is not None else True
        )

    return result


@app.get("/vat/format-check")
def format_check(
    vat: str = Query(..., description="EU VAT number to check format only, e.g. DE123456789")
):
    """
    Check only the format of a VAT number without calling VIES.
    Faster and uses no external API calls. Good for real-time form validation.
    """
    vat = clean_vat(vat)
    result = validate_format(vat)

    return {
        "vat_number": vat,
        "country_code": result["country_code"],
        "country": result["country"],
        "format_valid": result["valid_format"],
        "error": result["error"],
        "note": "Format check only — use /vat/validate for full VIES verification"
    }


@app.post("/vat/bulk-validate")
async def bulk_validate(
    vat_numbers: List[str],
    check_vies: bool = Query(False, description="Check each number against VIES (slower but more accurate)")
):
    """
    Validate up to 20 VAT numbers in one request.
    VIES checking is optional for bulk — format-only is much faster.
    """
    if len(vat_numbers) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 VAT numbers per bulk request")

    results = []
    valid_count = 0
    invalid_count = 0

    for vat in vat_numbers:
        vat = clean_vat(vat)
        format_result = validate_format(vat)

        item = {
            "vat_number": vat,
            "country_code": format_result["country_code"],
            "country": format_result["country"],
            "format_valid": format_result["valid_format"],
            "is_valid": format_result["valid_format"],
            "error": format_result["error"]
        }

        if format_result["valid_format"] and check_vies:
            vies_result = await check_vies(format_result["country_code"], vat)
            item["vies_valid"] = vies_result["vies_valid"]
            item["company_name"] = vies_result["company_name"]
            item["is_valid"] = format_result["valid_format"] and (
                vies_result["vies_valid"] if vies_result["vies_valid"] is not None else True
            )

        if item["is_valid"]:
            valid_count += 1
        else:
            invalid_count += 1

        results.append(item)

    return {
        "total_processed": len(results),
        "summary": {
            "valid": valid_count,
            "invalid": invalid_count,
            "vies_checked": check_vies
        },
        "results": results
    }


@app.get("/vat/countries")
def list_countries():
    """
    List all supported EU countries and their VAT number format rules.
    """
    countries = []
    for code, name in COUNTRY_NAMES.items():
        countries.append({
            "country_code": code,
            "country": name,
            "vat_prefix": code,
            "example_format": VAT_PATTERNS[code].replace("^", "").replace("$", "").replace("\\d", "X").replace("[A-Z0-9]", "A").replace("[A-Z]", "A").replace("{", "").replace("}", "").replace("|", " or ")
        })

    return {
        "total_supported": len(countries),
        "countries": countries
    }
