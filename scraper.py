import requests
import scraperwiki
from datetime import datetime, timedelta

# -----------------------------------------------------------------------
# NSW Planning Portal – Online DA Open Data API
# Fetches all Development Applications lodged in the last 30 days and
# saves them to a morph.io SQLite database (data.sqlite, table: data).
#
# API docs: https://www.planningportal.nsw.gov.au/opendata/dataset/online-da-data-api
# Data dictionary: DA Open APIs v2.0 (DPIE)
#
# No subscription key is required for the public open-data endpoint.
# -----------------------------------------------------------------------

API_URL = "https://api.apps1.nsw.gov.au/planning/viewApplication/v3/OnlineDA"

# Date window: today and 30 days ago (format required by API: YYYY-MM-DD)
today = datetime.today()
thirty_days_ago = today - timedelta(days=30)

date_from = thirty_days_ago.strftime("%Y-%m-%d")
date_to   = today.strftime("%Y-%m-%d")

payload = {
    "filters": {
        "LodgementDateFrom": date_from,
        "LodgementDateTo":   date_to,
    },
    "filters_operator": "AND",
    "page_size": 500,       # max records per page; loop below handles pagination
    "page_number": 1,
    "sort": {
        "field": "LodgementDate",
        "direction": "DESC",
    },
}

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def fetch_page(page_number):
    payload["page_number"] = page_number
    response = requests.post(API_URL, json=payload, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.json()

def normalise(record):
    """
    Flatten the API response record into a dict that matches the
    DA Open APIs v2.0 data dictionary field names used as SQLite columns.
    The API may return nested dicts for address fields; we unpack them here.
    """
    address = record.get("Location", [{}])
    # The API returns a list of locations; take the first one
    loc = address[0] if isinstance(address, list) and address else {}

    return {
        # --- Core application fields ---
        "PlanningPortalApplicationNumber": record.get("PlanningPortalApplicationNumber"),
        "ApplicationType":                 record.get("ApplicationType"),
        "ApplicationStatus":               record.get("ApplicationStatus"),
        "ModificationApplicationNumber":   record.get("ModificationApplicationNumber"),
        "CouncilName":                     record.get("CouncilName"),
        "CouncilApplicationNumber":        record.get("CouncilApplicationNumber"),
        "DevelopmentType":                 record.get("DevelopmentType"),
        "DevelopmentCategory":             record.get("DevelopmentCategory"),
        "CostofDevelopment":               record.get("CostofDevelopment"),
        "NumberOfNewDwellings":            record.get("NumberOfNewDwellings"),
        "NumberOfStoreys":                 record.get("NumberOfStoreys"),
        "NumberOfExistingLots":            record.get("NumberOfExistingLots"),
        "SubdivisionProposedFlag":         record.get("SubdivisionProposedFlag"),
        "SubdivisionType":                 record.get("SubdivisionType"),
        "NumberOfProposedLots":            record.get("NumberOfProposedLots"),
        "EPIVariationProposedFlag":        record.get("EPIVariationProposedFlag"),
        "AccompaniedByVPAFlag":            record.get("AccompaniedByVPAFlag"),
        "VPAStatus":                       record.get("VPAStatus"),
        "DeterminationAuthority":          record.get("DeterminationAuthority"),
        "DeterminationDate":               record.get("DeterminationDate"),
        "LodgementDate":                   record.get("LodgementDate"),
        "SubmissionDate":                  record.get("SubmissionDate"),
        "AssessmentExhibitionStartDate":   record.get("AssessmentExhibitionStartDate"),
        "AssessmentExhibitionEndDate":     record.get("AssessmentExhibitionEndDate"),
        "DevelopmentSubjectToSICFlag":     record.get("DevelopmentSubjectToSICFlag"),
        "VariationToDevelopmentStandardsApprovedFlag": record.get("VariationToDevelopmentStandardsApprovedFlag"),
        "ApplicationLastUpdated":          record.get("ApplicationLastUpdated"),

        # --- Address / location fields (from Location[0]) ---
        "FullAddress":  loc.get("FullAddress"),
        "StreetNumber1": loc.get("StreetNumber1"),
        "StreetNumber2": loc.get("StreetNumber2"),
        "StreetName":   loc.get("StreetName"),
        "StreetType":   loc.get("StreetType"),
        "StreetSuffix": loc.get("StreetSuffix"),
        "Suburb":       loc.get("Suburb"),
        "Postcode":     loc.get("Postcode"),
        "State":        loc.get("State"),
        "X":            loc.get("X"),
        "Y":            loc.get("Y"),
        "Lot":          loc.get("Lot"),
        "PlanLabel":    loc.get("PlanLabel"),
        "Section":      loc.get("Section"),
    }

def main():
    page = 1
    total_saved = 0

    print(f"Fetching DAs lodged between {date_from} and {date_to} …")

    while True:
        print(f"  Fetching page {page} …")
        try:
            data = fetch_page(page)
        except requests.HTTPError as e:
            print(f"  HTTP error on page {page}: {e}")
            break
        except Exception as e:
            print(f"  Unexpected error on page {page}: {e}")
            break

        # The API returns results under various possible keys; try common ones
        records = (
            data.get("Application")
            or data.get("application")
            or data.get("data")
            or data.get("results")
            or []
        )

        if not records:
            print("  No more records – done.")
            break

        rows = [normalise(r) for r in records]

        scraperwiki.sqlite.save(
            unique_keys=["PlanningPortalApplicationNumber"],
            data=rows,
            table_name="data",
        )
        total_saved += len(rows)
        print(f"  Saved {len(rows)} records (total so far: {total_saved})")

        # If fewer records than page_size were returned, we're on the last page
        if len(records) < payload["page_size"]:
            break

        page += 1

    print(f"\nFinished. {total_saved} DA records saved to data.sqlite (table: data).")

if __name__ == "__main__":
    main()
