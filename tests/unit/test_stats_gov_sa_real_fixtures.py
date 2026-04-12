"""Regression tests backed by real recorded stats.gov.sa release-card fixtures."""

from __future__ import annotations

from pathlib import Path

from saudi_open_data_mcp.connectors.base import RawPayload
from saudi_open_data_mcp.normalization.pipeline import (
    NormalizationPipeline,
    NormalizationPipelineStatus,
)

CPI_PAGE_LOCATOR = "/en/news?q=inflation&delta=20&start=0"
GDP_PAGE_LOCATOR = "/en/news?q=gdp&delta=20&start=0"
UNEMPLOYMENT_PAGE_LOCATOR = "/en/news?q=unemployment&delta=20&start=0"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stats_gov_sa"
CPI_FIXTURES_DIR = FIXTURES_DIR / "cpi_headline_monthly"
GDP_FIXTURES_DIR = FIXTURES_DIR / "real_gdp_growth_quarterly"
UNEMPLOYMENT_FIXTURES_DIR = FIXTURES_DIR / "unemployment_rate_total_quarterly"


def _fixture_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _page_url(locator: str) -> str:
    return f"https://www.stats.gov.sa{locator}"


def _records_by_field(records, field_name: str) -> dict[str, dict[str, object]]:
    return {record.fields[field_name]: record.fields for record in records}


def test_real_cpi_release_card_fixture_normalizes_to_known_good_monthly_rows() -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id=CPI_PAGE_LOCATOR,
        content={
            "url": _page_url(CPI_PAGE_LOCATOR),
            "status_code": 200,
            "content_type": "text/html",
            "body": _fixture_text(
                CPI_FIXTURES_DIR / "inflation-release-cards.html"
            ),
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-cpi-headline-monthly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 3
    records_by_month = _records_by_field(result.records, "observation_month")

    # Manually verified against the recorded inflation release card for December 2025.
    assert records_by_month["2025-12"] == {
        "observation_month": "2025-12",
        "inflation_series_code": "headline_cpi_all_items",
        "inflation_series_name": "Headline CPI",
        "release_date": "2026-01-15",
        "yoy_rate_percent": 2.1,
        "mom_rate_percent": 0.1,
        "source_locator": CPI_PAGE_LOCATOR,
        "source_url": _page_url(CPI_PAGE_LOCATOR),
        "source_release_url": "https://www.stats.gov.sa/en/w/news/155",
        "source_release_title": (
            "GASTAT: Saudi Arabia's inflation rate records 2.1% in December 2025"
        ),
        "source_release_date_text": "15-01-2026",
        "source_summary_text": (
            "The annual inflation rate in Saudi Arabia reached 2.1% in December 2025, "
            "compared to December 2024, while it recorded a monthly increase of 0.1% "
            "compared to November 2025. In the same context, the Wholesale Price Index "
            "(WPI) increased by 3.1% in December 2025 compared to the same period in "
            "2024 and rose by 1.0% on a monthly basis. It is worth noting that the "
            "Consumer Price Index (CPI) reflects changes in prices paid by consumers "
            "for a fixed basket of 582 goods and services, while the Wholesale Price "
            "Index (WPI) measures the price movements of goods at pre-retail stages, "
            "based on a fixed basket of 343 items."
        ),
    }
    # Manually verified against the recorded inflation release card for November 2025.
    assert records_by_month["2025-11"] == {
        "observation_month": "2025-11",
        "inflation_series_code": "headline_cpi_all_items",
        "inflation_series_name": "Headline CPI",
        "release_date": "2025-12-15",
        "yoy_rate_percent": 1.9,
        "mom_rate_percent": 0.1,
        "source_locator": CPI_PAGE_LOCATOR,
        "source_url": _page_url(CPI_PAGE_LOCATOR),
        "source_release_url": "https://www.stats.gov.sa/en/w/news/136",
        "source_release_title": (
            "GASTAT: Inflation in Saudi Arabia reaches 1.9% in November 2025"
        ),
        "source_release_date_text": "15-12-2025",
        "source_summary_text": (
            "The annual inflation rate of the Consumer Price Index (CPI) in Saudi "
            "Arabia reached 1.9% in November 2025, compared with November 2024, "
            "recording relative stability on a monthly basis at 0.1% compared with "
            "October 2025. Meanwhile, the Wholesale Price Index (WPI) recorded an "
            "annual increase of 2.3% in November 2025, compared with the same month "
            "in 2024, while the index recorded a monthly decline of 0.3% compared with "
            "October 2025. It is noteworthy that CPI reflects changes in the prices "
            "paid by consumers for a fixed basket of 582 items, while WPI reflects "
            "movements in the prices of goods at the pre-retail stage for a fixed "
            "basket of 343 items."
        ),
    }
    assert records_by_month["2025-10"]["release_date"] == "2025-11-13"
    assert records_by_month["2025-10"]["yoy_rate_percent"] == 2.2
    assert records_by_month["2025-10"]["mom_rate_percent"] == 0.3


def test_real_gdp_release_card_fixture_normalizes_to_known_good_quarterly_rows() -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id=GDP_PAGE_LOCATOR,
        content={
            "url": _page_url(GDP_PAGE_LOCATOR),
            "status_code": 200,
            "content_type": "text/html",
            "body": _fixture_text(GDP_FIXTURES_DIR / "gdp-release-cards.html"),
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-real-gdp-growth-quarterly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 3
    records_by_quarter = _records_by_field(result.records, "observation_quarter")

    # Manually verified against the recorded flash GDP release cards.
    assert records_by_quarter["2025-Q2"] == {
        "observation_quarter": "2025-Q2",
        "gdp_series_code": "real_gdp_growth_rate_yoy",
        "gdp_series_name": "Real GDP Growth Rate (Year-on-Year)",
        "release_date": "2025-07-31",
        "value_percent": 3.9,
        "source_locator": GDP_PAGE_LOCATOR,
        "source_url": _page_url(GDP_PAGE_LOCATOR),
        "source_release_url": "https://www.stats.gov.sa/en/w/news/71",
        "source_release_title": "GASTAT Real GDP grows by 3.9% in Q2 of 2025",
        "source_release_date_text": "31-07-2025",
        "source_summary_text": (
            "The General Authority for Statistics (GASTAT) released flash estimates "
            "for the Gross Domestic Product (GDP) for Q2 of 2025. The real GDP grew "
            "by 3.9% compared to the same period in 2024. Non-oil activities recorded "
            "a growth of 4.7%, oil activities grew by 3.8%, while government "
            "activities increased by 0.6%, according to the publication's results. "
            "The publication also showed that seasonally adjusted real GDP increased "
            "by 2.1% compared to Q1 of 2025. Oil activities recorded a growth of 5.6%, "
            "non-oil activities increased by 1.6%, while government activities "
            "decreased by 0.8%. It is worth noting that the flash (quarterly) GDP "
            "estimates are preliminary assessments of real growth rates, released "
            "shortly after the end of the reference quarter when complete data is not "
            "yet available. GASTAT will publish the final results once all data has "
            "been collected and verified."
        ),
    }
    assert records_by_quarter["2025-Q1"] == {
        "observation_quarter": "2025-Q1",
        "gdp_series_code": "real_gdp_growth_rate_yoy",
        "gdp_series_name": "Real GDP Growth Rate (Year-on-Year)",
        "release_date": "2025-06-09",
        "value_percent": 3.4,
        "source_locator": GDP_PAGE_LOCATOR,
        "source_url": _page_url(GDP_PAGE_LOCATOR),
        "source_release_url": "https://www.stats.gov.sa/en/w/news/50",
        "source_release_title": "GASTAT Real GDP grows by 3.4% in Q1 2025",
        "source_release_date_text": "09-06-2025",
        "source_summary_text": (
            "The General Authority for Statistics (GASTAT) released the Gross "
            "Domestic Product (GDP) report for the first quarter of 2025. According "
            "to the publication's results, real GDP achieved a growth rate of 3.4% "
            "compared to the same quarter of 2024, driven by a 4.9% growth in "
            "non-oil activities, in addition to a 3.2% growth in government "
            "activities, while oil activities recorded a decline of 0.5%. Meanwhile, "
            "seasonally adjusted real GDP rose by 1.1% compared to the fourth quarter "
            "of 2024. The results also showed that non-oil activities are the main "
            "driver to the annual real GDP growth, contributing 2.8 percentage "
            "points. Additionally, government activities and net taxes on products "
            "contributed positively by 0.5 and 0.2 percentage points, respectively. "
            "It is worth noting that most economic activities achieved positive annual "
            "growth rates. Wholesale and retail trade, restaurants, and hotels "
            "recorded the highest growth rates during the first quarter of 2025, "
            "reaching 8.4% year-on-year and 0.7% quarter-on-quarter."
        ),
    }
    assert records_by_quarter["2024-Q4"]["release_date"] == "2025-01-30"
    assert records_by_quarter["2024-Q4"]["value_percent"] == 4.4
    assert (
        records_by_quarter["2024-Q4"]["source_release_url"]
        == "https://www.stats.gov.sa/en/w/news/15"
    )


def test_real_unemployment_release_card_fixture_normalizes_to_known_good_quarterly_rows() -> None:
    raw_payload = RawPayload(
        source="stats-gov-sa",
        dataset_id=UNEMPLOYMENT_PAGE_LOCATOR,
        content={
            "url": _page_url(UNEMPLOYMENT_PAGE_LOCATOR),
            "status_code": 200,
            "content_type": "text/html",
            "body": _fixture_text(
                UNEMPLOYMENT_FIXTURES_DIR / "unemployment-release-cards.html"
            ),
        },
    )

    result = NormalizationPipeline().normalize(
        raw_payload,
        canonical_dataset_id="stats-gov-sa-unemployment-rate-total-quarterly",
    )

    assert result.status is NormalizationPipelineStatus.RECORD_DERIVABLE
    assert len(result.records) == 2
    records_by_quarter = _records_by_field(result.records, "observation_quarter")

    # Manually verified against the recorded labor-market release cards.
    assert records_by_quarter["2025-Q2"] == {
        "observation_quarter": "2025-Q2",
        "labor_series_code": "unemployment_rate_total_population_15_plus",
        "labor_series_name": "Unemployment Rate of Total Population (15+)",
        "release_date": "2025-09-30",
        "value_percent": 3.2,
        "source_locator": UNEMPLOYMENT_PAGE_LOCATOR,
        "source_url": _page_url(UNEMPLOYMENT_PAGE_LOCATOR),
        "source_release_url": "https://www.stats.gov.sa/en/w/news/93",
        "source_release_title": "GASTAT publishes Labor Market Statistics for Q2 of 2025",
        "source_release_date_text": "30-09-2025",
        "source_summary_text": (
            "GASTAT released Labor Market Statistics Publication for Q2 of 2025. "
            "Overall labor force participation rate (for Saudis and non-Saudis) "
            "reached 67.1%, while the overall unemployment rate (for Saudis and "
            "non-Saudis) reached 3.2%. Labor force participation rate among Saudis "
            "was 49.2%, and the unemployment rate among Saudis was 6.8%, according "
            "to the publication. The labor force participation rate among Saudi males "
            "was 64.0%, while the unemployment rate among Saudi males reached 4.3%. "
            "The results also indicated that the labor force participation rate among "
            "Saudi females was 34.5%, whereas the unemployment rate among Saudi "
            "females was 11.3%. The results related to young Saudi females (aged "
            "15-24 years) showed that the employment to population ratio reached "
            "13.8%, while their labor force participation rate was recorded at 17.4%. "
            "In comparison, the unemployment to population ratio among young Saudi "
            "males was 28.0%, and their labor force participation rate was 31.6%, "
            "the publication results noted. As for the labor market indicators in Q2 "
            "of 2025 concerning Saudi population (both males and females) in the core "
            "working age group (25-54 years), the employment to population ratio was "
            "63.3%, while the labor force participation rate reached 67.3%. The "
            "results further indicated that the unemployment rate reached 5.9%. "
            "Regarding the job search methods, it is noteworthy that the Labor Market "
            "Statistics Publication for Q2 of 2025 indicated that the most commonly "
            "used method was applying directly to employers, at a rate of 72.4%. "
            "This was followed by using the national unified employment platform "
            "(Jadarat) at 56.3%, while the method of asking friends or relatives "
            "about job opportunities constituted 50.5%."
        ),
    }
    assert records_by_quarter["2025-Q1"] == {
        "observation_quarter": "2025-Q1",
        "labor_series_code": "unemployment_rate_total_population_15_plus",
        "labor_series_name": "Unemployment Rate of Total Population (15+)",
        "release_date": "2025-06-29",
        "value_percent": 2.8,
        "source_locator": UNEMPLOYMENT_PAGE_LOCATOR,
        "source_url": _page_url(UNEMPLOYMENT_PAGE_LOCATOR),
        "source_release_url": "https://www.stats.gov.sa/en/w/news/56",
        "source_release_title": "Unemployment rate of total population reaches 2.8% in Q1 2025",
        "source_release_date_text": "29-06-2025",
        "source_summary_text": (
            "The General Authority for Statistics (GASTAT) released today the Labor "
            "Market Statistics Publication for Q1 of 2025. According to the results, "
            "the overall unemployment rate (including Saudis and non-Saudis) stood "
            "at 2.8%, while the overall labor force participation rate reached 68.2%. "
            "The labor force participation rate for Saudis increased to 51.3%, "
            "compared to Q4 of 2024. The publication showed a rise in labor force "
            "participation among Saudi males, reaching 66.4%, accompanied by a "
            "decline in their unemployment rate to 4%. It also highlighted the "
            "success of women's empowerment initiatives, which contributed to "
            "increased female economic participation and enhanced their role in "
            "driving growth and sustainable development. The labor force "
            "participation rate for Saudi females rose to 36.3%, while their "
            "unemployment rate dropped to 10.5%, compared to the previous quarter. "
            "Among young Saudi women (15–24 years), the employment-to-population "
            "ratio increased to 14.6%, and their labor force participation rose to "
            "18.4%. Meanwhile, the employment-to-population ratio for young Saudi "
            "males declined to 29.2%, with their labor force participation falling "
            "to 33.0%. Their unemployment rate dropped to 11.6% compared to Q4 of "
            "2024. These changes are attributed to improvements in labor market "
            "policies, driven by the robust performance and growing attractiveness "
            "of the Saudi labor market. Regarding core working-age Saudis (25–54 "
            "years), the employment-to-population ratio rose to 65.9%, and the "
            "labor force participation rate increased to 69.6%, while the "
            "unemployment rate declined to 5.4%. For Saudis (55 years and older), "
            "both the unemployment rate and labor force participation rate decreased "
            "compared to the previous quarter of 2024. According to the publication, "
            "the unemployment rate among Saudis reached a historic low of 6.3% in "
            "Q1 of 2025. Likewise, unemployment among Saudi women has declined by "
            "more than 11 percentage points since 2021, reaching 10.5%, reflecting "
            "the Saudi labor market's growing capacity to provide economic "
            "opportunities for its citizens amid supportive policies focused on "
            "development and employment. The most common job search method was "
            "directly approaching employers, used by 75.8% of job seekers, followed "
            "by using the national unified employment platform (Jadarat) at 74.6%, "
            "while 64.5% of job seekers reported posting or updating their resumes "
            "on professional social media platforms."
        ),
    }
