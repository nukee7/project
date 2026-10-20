"""Identity resolution using BSE India company list.

Resolves company name or ticker → BSE scrip code, company name,
exchange listing, and ISIN. Uses the BSE company search API.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import httpx

from shared.domain.identity import (
    ExchangeListing,
    IdentityResolution,
    IssuerIdentity,
    SecurityIdentity,
)
from shared.tools.identity import ResolveIssuerSecurity

logger = logging.getLogger(__name__)


class BseIdentityResolver(ResolveIssuerSecurity):
    """Resolve issuer/security using BSE India company search API."""

    COMPANY_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/Complainces/GetCompanyList"

    def __init__(self) -> None:
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
        }

    async def resolve(
        self,
        issuer_candidate: str,
        security_candidate: str | None = None,
        exchange_hint: str | None = None,
        as_of_date: date | None = None,
    ) -> IdentityResolution:
        logger.info("Resolving identity: issuer='%s', security='%s'", issuer_candidate, security_candidate)

        # Search by ticker first if provided, then by name
        search_terms = []
        if security_candidate:
            search_terms.append(security_candidate.strip())
        search_terms.append(issuer_candidate.replace("Ltd.", "").replace("Limited", "").strip())

        candidates: list[dict] = []

        for term in search_terms:
            try:
                results = await self._search_bse(term)
                if results:
                    candidates.extend(results)
                    break
            except Exception as e:
                logger.warning("BSE search failed for '%s': %s", term, e)

            # Try shorter name
            short = term.split()[0] if term else ""
            if short and short != term:
                try:
                    results = await self._search_bse(short)
                    if results:
                        candidates.extend(results)
                        break
                except Exception as e:
                    logger.warning("BSE search failed for '%s': %s", short, e)

        if not candidates:
            logger.warning("No candidates found for '%s'", issuer_candidate)
            return IdentityResolution(
                candidates_considered=[issuer_candidate],
                confidence="unresolved",
                unresolved_ambiguity=f"No BSE company found matching '{issuer_candidate}'",
                as_of_date=as_of_date or date.today(),
            )

        # Pick the best match
        best = candidates[0]
        scrip_code = best.get("scrip_code", "")
        company_name = best.get("company_name", issuer_candidate)
        isin = best.get("isin", "")
        ticker = security_candidate or scrip_code

        # Determine confidence
        name_lower = issuer_candidate.lower()
        match_lower = company_name.lower()
        if name_lower in match_lower or match_lower in name_lower:
            confidence = "high"
        elif security_candidate and security_candidate.upper() == scrip_code:
            confidence = "high"
        else:
            confidence = "medium"

        ambiguity = None
        if len(candidates) > 1:
            other_names = [c.get("company_name", "") for c in candidates[1:3]]
            ambiguity = f"Other matches: {', '.join(other_names)}"
            if confidence == "high" and len(candidates) > 3:
                confidence = "medium"

        issuer = IssuerIdentity(
            name=company_name,
            identifiers={
                "BSE_SCRIP": scrip_code,
                "ISIN": isin,
            },
            country_of_incorporation="IN",
        )

        security = SecurityIdentity(
            issuer=issuer,
            listings=[
                ExchangeListing(
                    exchange="BSE",
                    ticker=scrip_code,
                    currency="INR",
                    instrument_type="common",
                )
            ],
            isin=isin or None,
        )

        logger.info(
            "Resolved: '%s' → %s (scrip=%s, confidence=%s)",
            issuer_candidate, company_name, scrip_code, confidence,
        )

        return IdentityResolution(
            resolved_issuer=issuer,
            resolved_security=security,
            candidates_considered=[c.get("company_name", "") for c in candidates[:5]],
            resolution_source="BSE India Company Search",
            confidence=confidence,
            unresolved_ambiguity=ambiguity,
            as_of_date=as_of_date or date.today(),
        )

    async def _search_bse(self, search_term: str) -> list[dict]:
        """Search BSE for companies matching the term."""
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(self.COMPANY_SEARCH_URL, params={"search": search_term})
            resp.raise_for_status()
            text = resp.text.strip()

        if not text or text == "[]":
            return []

        results: list[dict] = []
        if text.startswith("["):
            data = json.loads(text)
            for item in data[:10]:
                results.append({
                    "scrip_code": str(
                        item.get("SCRIP_CD") or item.get("scrip_cd")
                        or item.get("ScripCode") or item.get("scripcode") or ""
                    ),
                    "company_name": (
                        item.get("LONG_NAME") or item.get("long_name")
                        or item.get("scrip_name") or item.get("SCRIP_NAME") or ""
                    ),
                    "isin": item.get("ISIN_NUMBER") or item.get("isin_number") or "",
                })
        else:
            # Pipe-delimited fallback
            for line in text.strip().split("\n")[:10]:
                parts = line.split("|")
                if len(parts) >= 2:
                    results.append({
                        "scrip_code": parts[0].strip(),
                        "company_name": parts[1].strip(),
                        "isin": parts[2].strip() if len(parts) > 2 else "",
                    })

        return results
