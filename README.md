# VATGuard API

Validate EU VAT numbers using the official VIES system. Check format, verify existence, and retrieve company details.

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/vat/validate` | GET | Full validation with VIES lookup |
| `/vat/format-check` | GET | Format-only check, instant response |
| `/vat/bulk-validate` | POST | Validate up to 20 VAT numbers at once |
| `/vat/countries` | GET | List all supported EU countries |

## Supported Countries

27 EU member states + Northern Ireland (XI)

## Quick Start

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs at `http://localhost:8000/docs`

## Example

```
GET /vat/validate?vat=DE123456789
```
