from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill

from .models import MatchResult


EXPORT_COLUMNS = [
    "Rank",
    "Match score",
    "Skill score",
    "Role-title score",
    "Text similarity",
    "Experience score",
    "Location score",
    "Job title",
    "Company",
    "Location",
    "Country",
    "Required years",
    "Matched skills",
    "Missing skills",
    "Official job URL",
    "Apply URL",
    "Provider",
    "Published/updated",
]


def results_to_dataframe(results: list[MatchResult]) -> pd.DataFrame:
    rows = []
    for rank, result in enumerate(results, start=1):
        rows.append(
            {
                "Rank": rank,
                "Match score": result.match_score,
                "Skill score": result.skill_score,
                "Role-title score": result.role_score,
                "Text similarity": result.text_score,
                "Experience score": result.experience_score,
                "Location score": result.location_score,
                "Job title": result.job.title,
                "Company": result.job.company,
                "Location": result.job.location,
                "Country": result.detected_country,
                "Required years": result.required_years,
                "Matched skills": ", ".join(result.matched_skills),
                "Missing skills": ", ".join(result.missing_skills),
                "Official job URL": result.job.job_url,
                "Apply URL": result.job.apply_url or result.job.job_url,
                "Provider": result.job.provider,
                "Published/updated": result.job.published_at,
            }
        )
    return pd.DataFrame(rows, columns=EXPORT_COLUMNS)


def build_excel(results: list[MatchResult]) -> bytes:
    dataframe = results_to_dataframe(results)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Job matches")
        summary = pd.DataFrame(
            [
                ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
                ("Number of jobs", len(results)),
                ("Skill weight", "40%"),
                ("Role-title weight", "20%"),
                ("Text-similarity weight", "15%"),
                ("Experience weight", "15%"),
                ("Location weight", "10%"),
                ("Important", "Scores support review; they are not hiring probabilities."),
            ],
            columns=["Item", "Value"],
        )
        summary.to_excel(writer, index=False, sheet_name="Method")

        sheet = writer.book["Job matches"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        header_fill = PatternFill("solid", fgColor="1F4E78")
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center")

        widths = {
            "A": 8, "B": 14, "C": 13, "D": 16, "E": 16, "F": 17,
            "G": 15, "H": 38, "I": 22, "J": 28, "K": 14, "L": 15,
            "M": 42, "N": 42, "O": 48, "P": 48, "Q": 14, "R": 22,
        }
        for column, width in widths.items():
            sheet.column_dimensions[column].width = width

        for row in range(2, sheet.max_row + 1):
            for column in (15, 16):
                cell = sheet.cell(row=row, column=column)
                if cell.value:
                    cell.hyperlink = str(cell.value)
                    cell.style = "Hyperlink"
            for column in range(1, sheet.max_column + 1):
                sheet.cell(row=row, column=column).alignment = Alignment(
                    vertical="top", wrap_text=column in (8, 10, 13, 14)
                )

        if sheet.max_row >= 2:
            sheet.conditional_formatting.add(
                f"B2:B{sheet.max_row}",
                ColorScaleRule(
                    start_type="num", start_value=0, start_color="F8696B",
                    mid_type="num", mid_value=60, mid_color="FFEB84",
                    end_type="num", end_value=100, end_color="63BE7B",
                ),
            )

        method_sheet = writer.book["Method"]
        method_sheet.column_dimensions["A"].width = 28
        method_sheet.column_dimensions["B"].width = 70
        for cell in method_sheet[1]:
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)

    return output.getvalue()
