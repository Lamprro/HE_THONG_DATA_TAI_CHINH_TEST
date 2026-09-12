from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CompanyCandidate:
    company_id: str
    security_id: str | None
    symbol: str | None
    terms: tuple[str, ...]


class NewsCompanyMatcher:
    """Deterministic company matcher; it deliberately does not use an LLM."""

    MIN_TERM_LENGTH = 3

    def match_article(self, conn, article_id: str) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT article.id::text, article.title, article.sapo,
                       article.content_text, raw.security_id::text AS raw_security_id
                FROM news_articles article
                LEFT JOIN raw_payloads raw ON raw.id = article.raw_payload_id
                WHERE article.id = %s::uuid
                """,
                (article_id,),
            )
            article = cur.fetchone()
        if article is None:
            return 0

        candidates = self._candidates(conn)
        matches = self._find_matches(article, candidates)
        for company_id, security_id, score in matches:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO news_article_companies (
                        news_article_id, company_id, security_id,
                        relevance_score, match_method
                    ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'RULE')
                    ON CONFLICT (news_article_id, company_id) DO UPDATE
                    SET relevance_score = GREATEST(
                            news_article_companies.relevance_score,
                            EXCLUDED.relevance_score
                        ),
                        security_id = COALESCE(
                            news_article_companies.security_id,
                            EXCLUDED.security_id
                        ),
                        match_method = 'RULE'
                    """,
                    (article_id, company_id, security_id, score),
                )
        return len(matches)

    @classmethod
    def _candidates(cls, conn) -> list[CompanyCandidate]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT company.id::text AS company_id,
                       security.id::text AS security_id,
                       security.symbol,
                       company.company_code, company.legal_name, company.short_name,
                       alias.alias
                FROM companies company
                LEFT JOIN company_aliases alias ON alias.company_id = company.id
                LEFT JOIN securities security ON security.company_id = company.id
                WHERE company.is_active = true
                """
            )
            rows = cur.fetchall()

        grouped: dict[tuple[str, str | None, str | None], set[str]] = {}
        for row in rows:
            key = (row["company_id"], row["security_id"], row["symbol"])
            terms = grouped.setdefault(key, set())
            for value in (row["symbol"], row["company_code"], row["legal_name"], row["short_name"], row["alias"]):
                if value and len(value.strip()) >= cls.MIN_TERM_LENGTH:
                    terms.add(value.strip())
        return [CompanyCandidate(*key, tuple(terms)) for key, terms in grouped.items()]

    def _find_matches(self, article, candidates: list[CompanyCandidate]) -> list[tuple[str, str | None, float]]:
        title = " ".join(part for part in (article["title"], article["sapo"]) if part)
        body = article["content_text"] or ""
        raw_security_id = article["raw_security_id"]
        best: dict[str, tuple[str | None, float]] = {}

        for candidate in candidates:
            score = 0.0
            matched_symbol = False
            for term in candidate.terms:
                if self._contains(title, term):
                    is_symbol = self._is_symbol(term, candidate.symbol)
                    score = max(score, 1.0 if is_symbol else 0.90)
                    matched_symbol = matched_symbol or is_symbol
                elif self._contains(body, term):
                    is_symbol = self._is_symbol(term, candidate.symbol)
                    score = max(score, 0.70 if is_symbol else 0.60)
                    matched_symbol = matched_symbol or is_symbol
            if score == 0:
                continue
            # Do not attach an arbitrary listed security when the evidence is
            # only a company name. Attach one for an explicit ticker, or reuse
            # the raw payload security when it belongs to this company.
            security_id = raw_security_id if raw_security_id == candidate.security_id else (
                candidate.security_id if matched_symbol else None
            )
            current = best.get(candidate.company_id)
            if current is None or score > current[1] or (
                score == current[1] and current[0] is None and security_id is not None
            ):
                best[candidate.company_id] = (security_id, score)
        return [(company_id, security_id, score) for company_id, (security_id, score) in best.items()]

    @staticmethod
    def _contains(text: str, term: str) -> bool:
        return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, flags=re.IGNORECASE) is not None

    @staticmethod
    def _is_symbol(term: str, symbol: str | None) -> bool:
        return symbol is not None and term.casefold() == symbol.casefold()


news_company_matcher = NewsCompanyMatcher()
