"""SEC EDGAR search implementation.

Uses two EDGAR endpoints:
1. Company submissions API (data.sec.gov/submissions/) — get filing list for a known CIK
2. EDGAR full-text search (efts.sec.gov/LATEST/search-index) — search by company name

SEC EDGAR requires a User-Agent header with your name and email.
Set via EDGAR_USER_AGENT env var or pass to constructor.
Default: "CompanyAgent research@example.com"
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime

import httpx

from shared.domain.enums import SourceTier
from shared.domain.evidence import SourceMetadata
from company_agent.tools.base import SearchPrimarySources, SourceSearchResult

logger = logging.getLogger(__name__)

# Filing type → source tier mapping
FILING_TIERS: dict[str, SourceTier] = {
    "10-K": SourceTier.PRIMARY_FILING,
    "10-K/A": SourceTier.PRIMARY_FILING,
    "10-Q": SourceTier.PRIMARY_FILING,
    "10-Q/A": SourceTier.PRIMARY_FILING,
    "8-K": SourceTier.PRIMARY_ISSUER,
    "20-F": SourceTier.PRIMARY_FILING,
    "6-K": SourceTier.PRIMARY_ISSUER,
}

# Source type names from our plan → EDGAR form types
SOURCE_TYPE_TO_FORMS: dict[str, list[str]] = {
    "regulatory_filings": ["10-K", "10-Q", "20-F"],
    "earnings_releases": ["8-K"],
    "earnings_transcripts": [],  # Not available on EDGAR
    "investor_presentations": [],  # Not available on EDGAR
    "secondary_reporting": [],
    "analyst_opinion": [],
}


class EdgarSearchSources(SearchPrimarySources):
    """Search SEC EDGAR for company filings.

    Uses the EDGAR company submissions API to find filings
    for a given company by CIK or name.
    """

    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    COMPANY_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
    COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    def __init__(self, user_agent: str | None = None) -> None:
        self._user_agent = user_agent or os.getenv(
            "EDGAR_USER_AGENT", "CompanyAgent research@example.com"
        )
        self._headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
        }

    async def search(
        self,
        issuer_name: str,
        issuer_identifiers: dict[str, str] | None = None,
        period_scope: str | None = None,
        source_types: list[str] | None = None,
        max_results: int = 20,
    ) -> SourceSearchResult:
        """Search EDGAR for filings matching the issuer and period."""
        logger.info(
            "EDGAR search: issuer=%s, identifiers=%s, period=%s",
            issuer_name, issuer_identifiers, period_scope,
        )

        # Determine which form types to search for
        form_types = self._resolve_form_types(source_types)

        # Try to get CIK from identifiers
        cik = None
        if issuer_identifiers:
            cik = issuer_identifiers.get("CIK") or issuer_identifiers.get("cik")

        # If no CIK, search by company name to find it
        if not cik:
            cik = await self._lookup_cik(issuer_name)

        if not cik:
            logger.warning("Could not find CIK for '%s'", issuer_name)
            return SourceSearchResult(
                sources=[],
                total_available=0,
                search_query=f"issuer={issuer_name}",
                notes=f"Could not resolve CIK for '{issuer_name}'",
            )

        # Fetch the company's filing history from EDGAR submissions API
        # Fetch extra to account for period filtering
        fetch_limit = max_results * 5
        filings = await self._fetch_submissions(cik, form_types, fetch_limit)

        # Filter by period scope if given
        if period_scope:
            filings = self._filter_by_period(filings, period_scope)

        sources = filings[:max_results]

        logger.info(
            "EDGAR search complete: found %d filings for CIK %s",
            len(sources), cik,
        )

        return SourceSearchResult(
            sources=sources,
            total_available=len(sources),
            search_query=f"CIK={cik} forms={form_types} period={period_scope}",
        )

    async def _lookup_cik(self, company_name: str) -> str | None:
        """Look up CIK by company name using EDGAR company tickers."""
        logger.info("Looking up CIK for '%s'", company_name)

        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                resp = await client.get(self.COMPANY_TICKERS_URL)
                resp.raise_for_status()
                data = resp.json()

            # data is {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
            name_lower = company_name.lower()
            for entry in data.values():
                title = entry.get("title", "").lower()
                if name_lower in title or title in name_lower:
                    cik = str(entry["cik_str"])
                    logger.info("Found CIK %s for '%s' (matched '%s')", cik, company_name, entry["title"])
                    return cik

            # Try partial match on ticker
            for entry in data.values():
                ticker = entry.get("ticker", "").lower()
                if name_lower == ticker:
                    cik = str(entry["cik_str"])
                    logger.info("Found CIK %s for ticker '%s'", cik, company_name)
                    return cik

        except Exception as e:
            logger.error("CIK lookup failed: %s", e)

        return None

    async def _fetch_submissions(
        self,
        cik: str,
        form_types: list[str],
        max_results: int,
    ) -> list[SourceMetadata]:
        """Fetch filing list from EDGAR submissions API."""
        # CIK must be zero-padded to 10 digits
        cik_padded = cik.zfill(10)
        url = self.SUBMISSIONS_URL.format(cik=cik_padded)

        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error("EDGAR submissions fetch failed for CIK %s: %s", cik, e)
            return []

        company_name = data.get("name", f"CIK {cik}")
        recent = data.get("filings", {}).get("recent", {})

        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        primary_doc_descriptions = recent.get("primaryDocDescription", [])
        reporting_dates = recent.get("reportDate", [])

        sources: list[SourceMetadata] = []
        for i in range(len(forms)):
            form = forms[i]

            # Filter by form type
            if form_types and form not in form_types:
                continue

            accession = accession_numbers[i].replace("-", "")
            filing_date_str = filing_dates[i]
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            report_date_str = reporting_dates[i] if i < len(reporting_dates) else ""
            description = primary_doc_descriptions[i] if i < len(primary_doc_descriptions) else form

            # Build filing URL
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"
            )

            # Parse dates
            try:
                filing_date = date.fromisoformat(filing_date_str)
            except (ValueError, TypeError):
                filing_date = None

            # Determine reporting period from report date
            reporting_period = report_date_str or None

            # Map form type to source tier
            tier = FILING_TIERS.get(form, SourceTier.PRIMARY_FILING)

            source = SourceMetadata(
                source_id=f"edgar_{accession}",
                publisher="SEC EDGAR",
                title=f"{company_name} — {form} ({filing_date_str})",
                source_url=filing_url,
                publication_date=filing_date,
                reporting_period=reporting_period,
                retrieval_time=datetime.now(),
                source_tier=tier,
                licensing_notes="Public domain — SEC EDGAR",
            )
            sources.append(source)

            if len(sources) >= max_results:
                break

        return sources

    @staticmethod
    def _resolve_form_types(source_types: list[str] | None) -> list[str]:
        """Convert our source type names to EDGAR form types."""
        if not source_types:
            return ["10-K", "10-Q", "8-K"]  # Default: annual, quarterly, current reports

        forms: list[str] = []
        for st in source_types:
            mapped = SOURCE_TYPE_TO_FORMS.get(st, [])
            forms.extend(mapped)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for f in forms:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        return unique or ["10-K", "10-Q", "8-K"]  # Fallback if no forms mapped

    @staticmethod
    def _filter_by_period(
        sources: list[SourceMetadata],
        period_scope: str,
    ) -> list[SourceMetadata]:
        """Filter filings by period scope string like 'FY2023-FY2024'.

        A 10-K for FY2024 is typically filed in early 2025, so we include
        filings dated up to 6 months after the max year (i.e., up to June of max_year+1).
        We also use the reporting_period (reportDate) when available.
        """
        import re
        years = re.findall(r"20\d{2}", period_scope)
        if not years:
            return sources

        min_year = int(min(years))
        max_year = int(max(years))

        filtered: list[SourceMetadata] = []
        for source in sources:
            # Prefer report date for filtering (it represents the fiscal period)
            if source.reporting_period:
                rp_years = re.findall(r"20\d{2}", source.reporting_period)
                if rp_years:
                    rp_year = int(max(rp_years))
                    if min_year <= rp_year <= max_year:
                        filtered.append(source)
                        continue

            # Fall back to filing date
            if source.publication_date:
                year = source.publication_date.year
                month = source.publication_date.month
                # Include filings from target years, plus Jan-Jun of max_year+1
                # (to catch annual filings for the max year)
                if min_year <= year <= max_year:
                    filtered.append(source)
                elif year == max_year + 1 and month <= 6:
                    filtered.append(source)
            else:
                filtered.append(source)

        return filtered
