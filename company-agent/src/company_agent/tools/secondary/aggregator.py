"""Secondary source aggregator — India-focused news + analyst + valuation data.

Combines:
1. Google News RSS (India) — recent news articles about the company
2. Yahoo Finance — analyst recommendations, key stats, valuation metrics

One Yahoo Finance call per ticker. The result is cached and serves both:
- search() → evidence records for the LLM (Step 3A)
- get_valuation() → structured valuation dict for the response (Step 6)

India-only. All tickers use .NS (NSE) or .BO (BSE) suffixes.
No API keys needed.
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
from company_agent.tools.base import SearchSecondarySources, GetValuationContext

logger = logging.getLogger(__name__)


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


class SecondarySourceAggregator(SearchSecondarySources, GetValuationContext):
    """Aggregates secondary reporting and valuation data.

    Implements both SearchSecondarySources (Step 3A) and
    GetValuationContext (Step 6) from a single Yahoo Finance call.
    """

    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    def __init__(self, yahoo_enabled: bool = True, news_enabled: bool = True) -> None:
        self._yahoo_enabled = yahoo_enabled
        self._news_enabled = news_enabled
        self._headers = {
            "User-Agent": "CompanyAgent/0.1 research-tool",
        }
        # Cache: ticker → Yahoo Finance info dict (one call, reused)
        self._yahoo_cache: dict[str, dict] = {}
        self._resolved_tickers: dict[str, str] = {}  # original → resolved

    # ------------------------------------------------------------------
    # SearchSecondarySources interface (Step 3A)
    # ------------------------------------------------------------------

    async def search(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        research_question: str | None = None,
        period_scope: str | None = None,
        max_results: int = 10,
        search_queries: list[str] | None = None,
    ) -> list[EvidenceRecord]:
        """Gather secondary evidence from news and Yahoo Finance."""
        logger.info(
            "Secondary search: issuer=%s, ticker=%s, planned_queries=%d",
            issuer_name, security_identifier, len(search_queries) if search_queries else 0,
        )

        records: list[EvidenceRecord] = []

        # 1. Google News
        if self._news_enabled:
            queries = search_queries or [f"{issuer_name} {security_identifier or ''} stock news"]
            news_per_query = max(1, (max_results // 2) // len(queries))

            for query in queries:
                try:
                    news_records = await self._fetch_google_news(
                        issuer_name, security_identifier,
                        max_results=news_per_query,
                        custom_query=query,
                    )
                    records.extend(news_records)
                except Exception as e:
                    logger.warning("Google News failed for '%s': %s", query, e)

            logger.info("Google News: %d articles from %d queries", len(records), len(queries))

        # 2. Yahoo Finance — fetch once, cache, build evidence records
        if self._yahoo_enabled and security_identifier:
            try:
                info = await self._get_yahoo_info(security_identifier)
                if info:
                    yahoo_records = self._build_yahoo_evidence(info, security_identifier, issuer_name)
                    records.extend(yahoo_records)
                    logger.info("Yahoo Finance: %d evidence records", len(yahoo_records))
            except Exception as e:
                logger.warning("Yahoo Finance failed: %s", e)

        logger.info("Secondary search complete: %d total for %s", len(records), issuer_name)
        return records[:max_results]

    # ------------------------------------------------------------------
    # GetValuationContext interface (Step 6)
    # ------------------------------------------------------------------

    async def get_valuation(
        self,
        issuer_name: str,
        security_identifier: str | None = None,
        as_of_date: object | None = None,
        metrics: list[str] | None = None,
    ) -> dict[str, object]:
        """Return structured valuation data from cached Yahoo Finance call."""
        if not security_identifier:
            return {"available": False, "reason": "No ticker provided"}

        info = await self._get_yahoo_info(security_identifier)
        if not info:
            return {"available": False, "reason": f"No Yahoo Finance data for {security_identifier}"}

        resolved = self._resolved_tickers.get(security_identifier, security_identifier)
        calc_id = f"val_{_uid()}"

        result: dict[str, object] = {
            "available": True,
            "calculation_id": calc_id,
            "ticker": resolved,
            "issuer_name": info.get("longName") or issuer_name,
            "currency": info.get("currency", "INR"),
            "as_of_date": str(as_of_date) if as_of_date else str(date.today()),
            "method": "Yahoo Finance market data",
            "inputs": f"Source: Yahoo Finance, ticker: {resolved}",
        }

        # Valuation ratios
        valuation: dict[str, object] = {}
        for key, label in [
            ("trailingPE", "trailing_pe"), ("forwardPE", "forward_pe"),
            ("priceToBook", "price_to_book"), ("priceToSalesTrailing12Months", "price_to_sales"),
            ("enterpriseToRevenue", "ev_to_revenue"), ("enterpriseToEbitda", "ev_to_ebitda"),
            ("pegRatio", "peg_ratio"),
        ]:
            if info.get(key):
                valuation[label] = round(info[key], 2)

        # Market data
        market: dict[str, object] = {}
        for key, label in [
            ("marketCap", "market_cap"), ("enterpriseValue", "enterprise_value"),
            ("currentPrice", "current_price"), ("fiftyTwoWeekHigh", "52_week_high"),
            ("fiftyTwoWeekLow", "52_week_low"),
        ]:
            if info.get(key):
                market[label] = info[key]
        if info.get("beta"):
            market["beta"] = round(info["beta"], 2)

        # Profitability (convert to percentages)
        profitability: dict[str, object] = {}
        for key, label in [
            ("profitMargins", "profit_margin"), ("operatingMargins", "operating_margin"),
            ("grossMargins", "gross_margin"), ("returnOnEquity", "roe"),
            ("returnOnAssets", "roa"),
        ]:
            if info.get(key):
                profitability[label] = round(info[key] * 100, 1)

        # Growth
        growth: dict[str, object] = {}
        for key, label in [
            ("revenueGrowth", "revenue_growth"), ("earningsGrowth", "earnings_growth"),
            ("earningsQuarterlyGrowth", "quarterly_earnings_growth"),
            ("revenueQuarterlyGrowth", "quarterly_revenue_growth"),
        ]:
            if info.get(key):
                growth[label] = round(info[key] * 100, 1)

        # Dividends
        dividends: dict[str, object] = {}
        for key, label in [
            ("dividendYield", "dividend_yield"),
            ("trailingAnnualDividendYield", "trailing_annual_yield"),
            ("payoutRatio", "payout_ratio"),
        ]:
            if info.get(key):
                dividends[label] = round(info[key] * 100, 2)

        # Financial health
        health: dict[str, object] = {}
        for key, label in [
            ("debtToEquity", "debt_to_equity"), ("currentRatio", "current_ratio"),
            ("quickRatio", "quick_ratio"), ("totalCashPerShare", "cash_per_share"),
        ]:
            if info.get(key):
                health[label] = round(info[key], 2)

        # Analyst
        analyst: dict[str, object] = {}
        for key, label in [
            ("recommendationKey", "recommendation"), ("numberOfAnalystOpinions", "num_analysts"),
            ("targetMeanPrice", "target_mean"), ("targetLowPrice", "target_low"),
            ("targetHighPrice", "target_high"),
        ]:
            if info.get(key):
                analyst[label] = info[key]

        # Summary
        parts: list[str] = []
        if valuation.get("trailing_pe"):
            parts.append(f"P/E: {valuation['trailing_pe']}")
        if valuation.get("ev_to_ebitda"):
            parts.append(f"EV/EBITDA: {valuation['ev_to_ebitda']}")
        if profitability.get("roe"):
            parts.append(f"ROE: {profitability['roe']}%")
        if growth.get("revenue_growth"):
            parts.append(f"Rev Growth: {growth['revenue_growth']}%")
        if analyst.get("recommendation"):
            parts.append(f"Analyst: {analyst['recommendation']}")

        result["summary"] = "; ".join(parts) if parts else "Limited data"
        result["valuation"] = valuation
        result["market"] = market
        result["profitability"] = profitability
        result["growth"] = growth
        result["dividends"] = dividends
        result["financial_health"] = health
        result["analyst"] = analyst

        return result

    # ------------------------------------------------------------------
    # Yahoo Finance — single cached call
    # ------------------------------------------------------------------

    async def _get_yahoo_info(self, ticker: str) -> dict | None:
        """Get Yahoo Finance info for a ticker. Caches the result."""
        if ticker in self._yahoo_cache:
            return self._yahoo_cache[ticker]

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed")
            return None

        # India-only: try .NS and .BO suffixes
        tickers_to_try = [ticker]
        if not ticker.endswith((".NS", ".BO")):
            tickers_to_try = [f"{ticker}.NS", f"{ticker}.BO"]

        for t in tickers_to_try:
            try:
                stock = yf.Ticker(t)
                info = stock.info or {}
                if info.get("marketCap"):
                    logger.info("Yahoo Finance: resolved %s → %s", ticker, t)
                    self._yahoo_cache[ticker] = info
                    self._resolved_tickers[ticker] = t
                    return info
            except Exception:
                continue

        logger.info("Yahoo Finance: no data for %s", ticker)
        self._yahoo_cache[ticker] = {}
        return None

    def _build_yahoo_evidence(
        self, info: dict, ticker: str, issuer_name: str,
    ) -> list[EvidenceRecord]:
        """Build evidence records from cached Yahoo Finance data."""
        records: list[EvidenceRecord] = []
        resolved = self._resolved_tickers.get(ticker, ticker)

        source = SourceMetadata(
            source_id=f"yahoo_{_uid()}",
            publisher="Yahoo Finance",
            title=f"{issuer_name} — Yahoo Finance",
            source_url=f"https://finance.yahoo.com/quote/{resolved}/",
            retrieval_time=datetime.now(),
            source_tier=SourceTier.SECONDARY_LICENSED,
            licensing_notes="Yahoo Finance — public data.",
        )

        # Analyst recommendations
        rec = info.get("recommendationKey", "")
        rec_count = info.get("numberOfAnalystOpinions", 0)
        if rec and rec_count:
            excerpt = f"Analyst consensus: {rec.upper()} ({rec_count} analysts)."
            target = info.get("targetMeanPrice")
            if target:
                excerpt += f" Mean target: {target}."
            low, high = info.get("targetLowPrice"), info.get("targetHighPrice")
            if low and high:
                excerpt += f" Range: {low} — {high}."
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}", source=source, excerpt=excerpt,
                locator="Yahoo Finance — Analyst Recommendations",
                extraction_confidence="medium", is_management_statement=False,
                tags=["analyst", "recommendation", "secondary"],
            ))

        # Key stats
        parts: list[str] = []
        for key, label in [
            ("trailingPE", "Trailing P/E"), ("forwardPE", "Forward P/E"),
            ("priceToBook", "P/B"), ("debtToEquity", "Debt/Equity"),
        ]:
            if info.get(key):
                parts.append(f"{label}: {info[key]:.1f}")
        for key, label in [
            ("returnOnEquity", "ROE"), ("revenueGrowth", "Revenue Growth"),
            ("earningsGrowth", "Earnings Growth"),
        ]:
            if info.get(key):
                parts.append(f"{label}: {info[key]:.1%}")
        if parts:
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}", source=source,
                excerpt=f"Key statistics for {issuer_name}: {'; '.join(parts)}.",
                locator="Yahoo Finance — Key Statistics",
                extraction_confidence="medium", is_management_statement=False,
                tags=["statistics", "valuation", "secondary"],
            ))

        # Business summary
        summary = info.get("longBusinessSummary", "")
        if summary:
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}", source=source,
                excerpt=summary[:1000],
                locator="Yahoo Finance — Business Summary",
                extraction_confidence="medium", is_management_statement=False,
                tags=["business_summary", "overview", "secondary"],
            ))

        return records

    # ------------------------------------------------------------------
    # Google News
    # ------------------------------------------------------------------

    async def _fetch_google_news(
        self, issuer_name: str, security_identifier: str | None,
        max_results: int = 5, custom_query: str | None = None,
    ) -> list[EvidenceRecord]:
        if custom_query:
            query = custom_query
        else:
            query = issuer_name
            if security_identifier:
                query += f" {security_identifier} stock"

        url = self.GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            xml_text = resp.text

        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []

        records: list[EvidenceRecord] = []
        for item in channel.findall("item")[:max_results]:
            title = _strip_html(item.findtext("title", ""))
            link = item.findtext("link", "")
            pub_date_str = item.findtext("pubDate", "")
            description = _strip_html(item.findtext("description", ""))

            publisher = "Google News"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                publisher = parts[1].strip()

            pub_date = None
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(
                        pub_date_str.strip(), "%a, %d %b %Y %H:%M:%S %Z"
                    ).date()
                except ValueError:
                    pass

            excerpt = title
            if description and description != title:
                excerpt = f"{title}. {description}"
            if not excerpt.strip():
                continue

            source = SourceMetadata(
                source_id=f"news_{_uid()}", publisher=publisher,
                title=title[:200], source_url=link, publication_date=pub_date,
                retrieval_time=datetime.now(), source_tier=SourceTier.SECONDARY_LICENSED,
                licensing_notes="Google News RSS — public feed.",
            )
            records.append(EvidenceRecord(
                evidence_id=f"ev_{_uid()}", source=source,
                excerpt=excerpt[:1000], locator=f"Google News: {publisher}",
                extraction_confidence="low", is_management_statement=False,
                is_forecast=False, scope_notes=issuer_name,
                tags=["news", "secondary", publisher.lower().replace(" ", "_")],
            ))

        return records
