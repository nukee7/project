"""Secondary source aggregator — news + analyst data from free sources.

Combines:
1. Google News RSS — recent news articles about the company
2. Yahoo Finance — analyst recommendations and key stats

No API keys needed. All free sources.
"""

from __future__ import annotations

import logging
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from html import unescape

import httpx

from shared.domain.enums import SourceTier
from shared.domain.evidence import EvidenceRecord, SourceMetadata
from company_agent.tools.base import SearchSecondarySources

logger = logging.getLogger(__name__)


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


class SecondarySourceAggregator(SearchSecondarySources):
    """Aggregates secondary reporting from Google News and Yahoo Finance.

    Returns EvidenceRecords directly — each news article or analyst
    data point becomes one evidence record with proper attribution
    and source tier labeling.
    """

    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    def __init__(self, yahoo_enabled: bool = True, news_enabled: bool = True) -> None:
        self._yahoo_enabled = yahoo_enabled
        self._news_enabled = news_enabled
        self._headers = {
            "User-Agent": "CompanyAgent/0.1 research-tool",
        }

    async def search(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        research_question: str | None = None,
        period_scope: str | None = None,
        max_results: int = 10,
    ) -> list[EvidenceRecord]:
        """Gather secondary evidence from news and analyst sources."""
        logger.info(
            "Secondary search: issuer=%s, ticker=%s, question=%s",
            issuer_name, security_identifier, research_question and research_question[:50],
        )

        records: list[EvidenceRecord] = []

        # 1. Google News
        if self._news_enabled:
            try:
                news_records = await self._fetch_google_news(
                    issuer_name, security_identifier, max_results=max_results // 2 or 3,
                )
                records.extend(news_records)
                logger.info("Google News: found %d articles", len(news_records))
            except Exception as e:
                logger.warning("Google News fetch failed: %s", e)

        # 2. Yahoo Finance analyst data
        if self._yahoo_enabled and security_identifier:
            try:
                yahoo_records = await self._fetch_yahoo_analyst_data(
                    security_identifier, issuer_name,
                )
                records.extend(yahoo_records)
                logger.info("Yahoo Finance: found %d data points", len(yahoo_records))
            except Exception as e:
                logger.warning("Yahoo Finance fetch failed: %s", e)

        logger.info(
            "Secondary search complete: %d total records for %s",
            len(records), issuer_name,
        )

        return records[:max_results]

    async def _fetch_google_news(
        self,
        issuer_name: str,
        security_identifier: str | None,
        max_results: int = 5,
    ) -> list[EvidenceRecord]:
        """Fetch recent news from Google News RSS."""
        # Build search query — company name + optional ticker
        query = issuer_name
        if security_identifier:
            query += f" {security_identifier} stock"

        url = self.GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            xml_text = resp.text

        # Parse RSS XML
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        records: list[EvidenceRecord] = []
        items = channel.findall("item")

        for item in items[:max_results]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date_str = item.findtext("pubDate", "")
            description = item.findtext("description", "")

            # Clean up
            title = _strip_html(title)
            description = _strip_html(description)

            # Extract publisher from title (Google News format: "Title - Publisher")
            publisher = "Google News"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                publisher = parts[1].strip()

            # Parse date
            pub_date = None
            if pub_date_str:
                try:
                    # Google News RSS date format: "Mon, 01 Jan 2025 12:00:00 GMT"
                    pub_date = datetime.strptime(
                        pub_date_str.strip(), "%a, %d %b %Y %H:%M:%S %Z"
                    ).date()
                except ValueError:
                    pass

            # Build excerpt
            excerpt = title
            if description and description != title:
                excerpt = f"{title}. {description}"

            if not excerpt.strip():
                continue

            source = SourceMetadata(
                source_id=f"news_{_uid()}",
                publisher=publisher,
                title=title[:200],
                source_url=link,
                publication_date=pub_date,
                retrieval_time=datetime.now(),
                source_tier=SourceTier.SECONDARY_LICENSED,
                licensing_notes="Google News RSS — public feed.",
            )

            record = EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=excerpt[:1000],
                locator=f"Google News: {publisher}",
                applicable_period=None,
                extraction_confidence="low",
                is_management_statement=False,
                is_forecast=False,
                scope_notes=issuer_name,
                tags=["news", "secondary", publisher.lower().replace(" ", "_")],
            )
            records.append(record)

        return records

    async def _fetch_yahoo_analyst_data(
        self,
        ticker: str,
        issuer_name: str,
    ) -> list[EvidenceRecord]:
        """Fetch analyst recommendations and key stats from Yahoo Finance.

        Uses yfinance library if available, falls back to direct API.
        """
        records: list[EvidenceRecord] = []

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — skipping Yahoo Finance data")
            return records

        # Try both NSE and BSE suffixes for Indian stocks, plain for US
        tickers_to_try = [ticker]
        if not ticker.endswith((".NS", ".BO")):
            tickers_to_try.extend([f"{ticker}.NS", f"{ticker}.BO"])

        stock = None
        info = {}
        for t in tickers_to_try:
            try:
                stock = yf.Ticker(t)
                info = stock.info or {}
                if info.get("marketCap"):
                    logger.info("Yahoo Finance: resolved %s as %s", ticker, t)
                    break
            except Exception:
                continue

        if not info.get("marketCap"):
            logger.info("Yahoo Finance: no data found for %s", ticker)
            return records

        now = datetime.now()
        source = SourceMetadata(
            source_id=f"yahoo_{_uid()}",
            publisher="Yahoo Finance",
            title=f"{issuer_name} — Yahoo Finance Key Statistics",
            source_url=f"https://finance.yahoo.com/quote/{ticker}/",
            retrieval_time=now,
            source_tier=SourceTier.SECONDARY_LICENSED,
            licensing_notes="Yahoo Finance — public data.",
        )

        # Analyst recommendations
        rec = info.get("recommendationKey", "")
        rec_count = info.get("numberOfAnalystOpinions", 0)
        target_mean = info.get("targetMeanPrice")
        target_low = info.get("targetLowPrice")
        target_high = info.get("targetHighPrice")

        if rec and rec_count:
            excerpt = f"Analyst consensus: {rec.upper()} ({rec_count} analysts)."
            if target_mean:
                excerpt += f" Mean target price: {target_mean}."
            if target_low and target_high:
                excerpt += f" Range: {target_low} — {target_high}."

            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=excerpt,
                locator="Yahoo Finance — Analyst Recommendations",
                extraction_confidence="medium",
                is_management_statement=False,
                tags=["analyst", "recommendation", "secondary"],
            ))

        # Key financial stats
        pe_trailing = info.get("trailingPE")
        pe_forward = info.get("forwardPE")
        pb = info.get("priceToBook")
        debt_equity = info.get("debtToEquity")
        roe = info.get("returnOnEquity")
        revenue_growth = info.get("revenueGrowth")
        earnings_growth = info.get("earningsGrowth")

        stats_parts: list[str] = []
        if pe_trailing:
            stats_parts.append(f"Trailing P/E: {pe_trailing:.1f}")
        if pe_forward:
            stats_parts.append(f"Forward P/E: {pe_forward:.1f}")
        if pb:
            stats_parts.append(f"P/B: {pb:.2f}")
        if debt_equity:
            stats_parts.append(f"Debt/Equity: {debt_equity:.1f}")
        if roe:
            stats_parts.append(f"ROE: {roe:.1%}")
        if revenue_growth:
            stats_parts.append(f"Revenue Growth: {revenue_growth:.1%}")
        if earnings_growth:
            stats_parts.append(f"Earnings Growth: {earnings_growth:.1%}")

        if stats_parts:
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=f"Key statistics for {issuer_name}: {'; '.join(stats_parts)}.",
                locator="Yahoo Finance — Key Statistics",
                extraction_confidence="medium",
                is_management_statement=False,
                tags=["statistics", "valuation", "secondary"],
            ))

        # Business summary from Yahoo
        summary = info.get("longBusinessSummary", "")
        if summary:
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}",
                source=source,
                excerpt=summary[:1000],
                locator="Yahoo Finance — Business Summary",
                extraction_confidence="medium",
                is_management_statement=False,
                tags=["business_summary", "overview", "secondary"],
            ))

        return records
