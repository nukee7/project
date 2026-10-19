"""Primary source search — BSE India filings.

Uses BSE India APIs to find corporate filings:
1. Company search → resolve company name to BSE scrip code
2. Financial results → quarterly/annual results
3. Corporate announcements → board meetings, dividends, material events

BSE India APIs are free and don't require API keys.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime

import httpx

from shared.domain.enums import SourceTier
from shared.domain.evidence import SourceMetadata
from company_agent.tools.base import SearchPrimarySources, SourceSearchResult

logger = logging.getLogger(__name__)

FILING_TIERS: dict[str, SourceTier] = {
    "annual_report": SourceTier.PRIMARY_FILING,
    "financial_result": SourceTier.PRIMARY_FILING,
    "board_meeting": SourceTier.PRIMARY_ISSUER,
    "corporate_announcement": SourceTier.PRIMARY_ISSUER,
    "shareholding": SourceTier.PRIMARY_FILING,
}


class PrimarySearchSources(SearchPrimarySources):
    """Search BSE India for company filings and announcements."""

    COMPANY_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/Complainces/GetCompanyList"
    FINANCIAL_RESULTS_URL = "https://api.bseindia.com/BseIndiaAPI/api/FinancialResult/FinancialResult"
    ANNOUNCEMENTS_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/GetAnnSubCategoryData"

    def __init__(self) -> None:
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
        }

    async def search(
        self,
        issuer_name: str,
        issuer_identifiers: dict[str, str] | None = None,
        period_scope: str | None = None,
        source_types: list[str] | None = None,
        max_results: int = 20,
    ) -> SourceSearchResult:
        logger.info("Primary search: issuer=%s, period=%s", issuer_name, period_scope)

        scrip_code = None
        if issuer_identifiers:
            scrip_code = (
                issuer_identifiers.get("BSE_SCRIP")
                or issuer_identifiers.get("bse_scrip")
                or issuer_identifiers.get("scrip_code")
            )

        if not scrip_code:
            scrip_code = await self._lookup_scrip_code(issuer_name)

        if not scrip_code:
            logger.warning("Could not find BSE scrip code for '%s'", issuer_name)
            return SourceSearchResult(
                sources=[], total_available=0,
                search_query=f"issuer={issuer_name}",
                notes=f"Could not resolve BSE scrip code for '{issuer_name}'",
            )

        sources: list[SourceMetadata] = []

        try:
            sources.extend(await self._fetch_financial_results(scrip_code, issuer_name))
        except Exception as e:
            logger.warning("Financial results fetch failed: %s", e)

        try:
            sources.extend(await self._fetch_announcements(scrip_code, issuer_name))
        except Exception as e:
            logger.warning("Announcements fetch failed: %s", e)

        if period_scope:
            sources = self._filter_by_period(sources, period_scope)

        sources.sort(key=lambda s: s.publication_date or date.min, reverse=True)
        result = sources[:max_results]

        logger.info("Primary search complete: %d filings for scrip %s", len(result), scrip_code)

        return SourceSearchResult(
            sources=result, total_available=len(result),
            search_query=f"scrip={scrip_code} period={period_scope}",
        )

    async def _lookup_scrip_code(self, company_name: str) -> str | None:
        logger.info("Looking up BSE scrip code for '%s'", company_name)
        search_term = company_name.replace("Ltd.", "").replace("Limited", "").strip()

        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
                resp = await client.get(self.COMPANY_SEARCH_URL, params={"search": search_term})
                resp.raise_for_status()
                text = resp.text.strip()

                if not text or text == "[]":
                    short_name = search_term.split()[0] if search_term else ""
                    if short_name and short_name != search_term:
                        resp = await client.get(self.COMPANY_SEARCH_URL, params={"search": short_name})
                        resp.raise_for_status()
                        text = resp.text.strip()

                if not text or text == "[]":
                    return None

                if text.startswith("["):
                    data = json.loads(text)
                    if data:
                        first = data[0]
                        scrip = str(
                            first.get("SCRIP_CD") or first.get("scrip_cd")
                            or first.get("ScripCode") or first.get("scripcode") or ""
                        )
                        if scrip:
                            company = first.get("LONG_NAME") or first.get("scrip_name") or ""
                            logger.info("Found scrip %s for '%s' (matched '%s')", scrip, company_name, company)
                            return scrip
                else:
                    lines = text.strip().split("\n")
                    if lines:
                        parts = lines[0].split("|")
                        if parts:
                            return parts[0].strip()

        except Exception as e:
            logger.error("BSE scrip code lookup failed: %s", e)

        return None

    async def _fetch_financial_results(self, scrip_code: str, company_name: str) -> list[SourceMetadata]:
        sources: list[SourceMetadata] = []
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
                resp = await client.get(self.FINANCIAL_RESULTS_URL, params={"scripcode": scrip_code})
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, list):
                data = data.get("Table", []) if isinstance(data, dict) else []

            for item in data:
                period = item.get("ResultType") or item.get("result_type") or item.get("Period") or "Unknown"
                filing_date_str = item.get("ResultDate") or item.get("result_date") or item.get("News_dt") or ""
                pdf_link = item.get("PDFLink") or item.get("pdflink") or item.get("Attachmentname") or ""

                pub_date = None
                if filing_date_str:
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
                        try:
                            pub_date = datetime.strptime(filing_date_str.strip(), fmt).date()
                            break
                        except ValueError:
                            continue

                url = pdf_link
                if url and not url.startswith("http"):
                    url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{url}"

                sources.append(SourceMetadata(
                    source_id=f"bse_fin_{scrip_code}_{len(sources)}",
                    publisher="BSE India",
                    title=f"{company_name} — Financial Result ({period})",
                    source_url=url or None,
                    publication_date=pub_date,
                    reporting_period=period,
                    retrieval_time=datetime.now(),
                    source_tier=SourceTier.PRIMARY_FILING,
                    licensing_notes="BSE India — public corporate filing",
                ))
        except Exception as e:
            logger.error("Financial results fetch failed for %s: %s", scrip_code, e)
        return sources

    async def _fetch_announcements(self, scrip_code: str, company_name: str) -> list[SourceMetadata]:
        sources: list[SourceMetadata] = []
        try:
            async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
                resp = await client.get(self.ANNOUNCEMENTS_URL, params={"scripcode": scrip_code, "strCat": "-1"})
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, list):
                data = data.get("Table", []) if isinstance(data, dict) else []

            for item in data[:20]:
                headline = item.get("HEADLINE") or item.get("headline") or item.get("NEWSSUB") or "Corporate Announcement"
                news_date_str = item.get("NEWS_DT") or item.get("DT_TM") or item.get("news_dt") or ""
                attachment = item.get("ATTACHMENTNAME") or item.get("attachmentname") or ""

                pub_date = None
                if news_date_str:
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y"):
                        try:
                            pub_date = datetime.strptime(news_date_str.strip()[:10], fmt).date()
                            break
                        except ValueError:
                            continue

                url = None
                if attachment:
                    url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attachment}"

                sources.append(SourceMetadata(
                    source_id=f"bse_ann_{scrip_code}_{len(sources)}",
                    publisher="BSE India",
                    title=f"{company_name} — {headline[:100]}",
                    source_url=url,
                    publication_date=pub_date,
                    retrieval_time=datetime.now(),
                    source_tier=SourceTier.PRIMARY_ISSUER,
                    licensing_notes="BSE India — corporate announcement",
                ))
        except Exception as e:
            logger.error("Announcements fetch failed for %s: %s", scrip_code, e)
        return sources

    @staticmethod
    def _filter_by_period(sources: list[SourceMetadata], period_scope: str) -> list[SourceMetadata]:
        years = re.findall(r"20\d{2}", period_scope)
        if not years:
            return sources
        min_year, max_year = int(min(years)), int(max(years))
        filtered: list[SourceMetadata] = []
        for source in sources:
            if source.reporting_period:
                rp_years = re.findall(r"20\d{2}", source.reporting_period)
                if rp_years and min_year <= int(max(rp_years)) <= max_year:
                    filtered.append(source)
                    continue
            if source.publication_date:
                y, m = source.publication_date.year, source.publication_date.month
                if min_year <= y <= max_year or (y == max_year + 1 and m <= 6):
                    filtered.append(source)
            else:
                filtered.append(source)
        return filtered
