from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest

import pandas as pd

import pharmacy_analysis as analysis


class AnalysisRegressionTests(unittest.TestCase):
    def test_return_offset_pair(self) -> None:
        config = analysis.DEFAULT_COLUMN_CONFIG
        frame = pd.DataFrame(
            [
                {
                    config.sales_bill_date: "2026-07-01",
                    config.sales_product_name: "药品A",
                    config.sales_price: 10,
                    config.sales_quantity: 1,
                    config.sales_amount: 10,
                    config.sales_approval_no: "A",
                },
                {
                    config.sales_bill_date: "2026-07-02",
                    config.sales_product_name: "药品A",
                    config.sales_price: 10,
                    config.sales_quantity: -1,
                    config.sales_amount: -10,
                    config.sales_approval_no: "A",
                },
            ]
        )
        with redirect_stdout(StringIO()):
            result, negative_rows, pairs, unmatched = analysis.mark_return_offsets(frame, config)
        self.assertEqual((negative_rows, pairs, unmatched), (1, 1, 0))
        self.assertEqual(result[config.sales_offset_id].tolist(), ["001", "001"])

    def test_prescription_drug_parenthetical_match(self) -> None:
        medical = pd.DataFrame([{analysis.COL_MEDICAL_PRODUCT_NAME: "罗红霉素分散片"}])
        catalog = pd.DataFrame(
            [{analysis.COL_PRESCRIPTION_DRUG_CATALOG_PRODUCT_NAME: "罗红霉素分散片(石药)"}]
        )
        with redirect_stdout(StringIO()):
            result, matched, unmatched = analysis.compare_medical_sales_to_prescription_drugs(
                medical, catalog
            )
        self.assertEqual((matched, unmatched), (1, 0))
        self.assertEqual(
            result.loc[0, analysis.COL_IS_PRESCRIPTION_DRUG],
            analysis.PRESCRIPTION_DRUG_MATCHED,
        )

    def test_medical_sales_detail_one_to_many_group_is_exact_match(self) -> None:
        config = analysis.DEFAULT_COLUMN_CONFIG
        medical = pd.DataFrame(
            [
                {
                    config.medical_product_name: "阿莫西林胶囊",
                    config.medical_settlement_time: "2026-01-01 14:00:00",
                    config.medical_amount: 10,
                },
                {
                    config.medical_product_name: "阿莫西林胶囊",
                    config.medical_settlement_time: "2026-01-01 14:01:00",
                    config.medical_amount: 10,
                },
            ]
        )
        sales = pd.DataFrame(
            [
                {
                    config.sales_product_name: "阿莫西林胶囊",
                    config.sales_bill_date: "2026-01-01 13:58:00",
                    config.sales_price: 20,
                }
            ]
        )

        with redirect_stdout(StringIO()):
            result, exact, incomplete, unmatched = (
                analysis.screen_medical_sales_details(medical, sales, config)
            )

        self.assertEqual((exact, incomplete, unmatched), (2, 0, 0))
        self.assertEqual(
            result.columns[-3:].tolist(),
            analysis.DETAIL_SCREEN_OUTPUT_COLUMNS,
        )
        self.assertEqual(
            result["比对结果"].tolist(),
            [analysis.MATCH_STATUS_EXACT, analysis.MATCH_STATUS_EXACT],
        )
        self.assertEqual(result["比对时间差"].tolist(), ["2分钟", "2分钟"])
        self.assertEqual(result["比对金额差"].tolist(), [0.0, 0.0])

    def test_medical_sales_detail_sales_rows_can_group_to_one_medical_row(self) -> None:
        config = analysis.DEFAULT_COLUMN_CONFIG
        medical = pd.DataFrame(
            [
                {
                    config.medical_product_name: "阿莫西林胶囊",
                    config.medical_settlement_time: "2026-01-01 14:00:00",
                    config.medical_amount: 20,
                }
            ]
        )
        sales = pd.DataFrame(
            [
                {
                    config.sales_product_name: "阿莫西林胶囊",
                    config.sales_bill_date: "2026-01-01 14:00:00",
                    config.sales_price: 10,
                },
                {
                    config.sales_product_name: "阿莫西林胶囊",
                    config.sales_bill_date: "2026-01-01 14:01:00",
                    config.sales_price: 10,
                },
            ]
        )

        with redirect_stdout(StringIO()):
            result, exact, incomplete, unmatched = (
                analysis.screen_medical_sales_details(medical, sales, config)
            )

        self.assertEqual((exact, incomplete, unmatched), (1, 0, 0))
        self.assertEqual(result.loc[0, "比对结果"], analysis.MATCH_STATUS_EXACT)

    def test_medical_sales_detail_fuzzy_incomplete_and_unmatched(self) -> None:
        config = analysis.DEFAULT_COLUMN_CONFIG
        medical = pd.DataFrame(
            [
                {
                    config.medical_product_name: "阿莫西林胶囊0.25g",
                    config.medical_settlement_time: "2026-01-02 09:00:00",
                    config.medical_amount: 10,
                },
                {
                    config.medical_product_name: "头孢克肟片",
                    config.medical_settlement_time: "2026-01-02 09:00:00",
                    config.medical_amount: 8,
                },
            ]
        )
        sales = pd.DataFrame(
            [
                {
                    config.sales_product_name: "阿莫西林胶囊",
                    config.sales_bill_date: "2026-01-01 09:00:00",
                    config.sales_price: 12,
                }
            ]
        )

        with redirect_stdout(StringIO()):
            result, exact, incomplete, unmatched = (
                analysis.screen_medical_sales_details(medical, sales, config)
            )

        self.assertEqual((exact, incomplete, unmatched), (0, 1, 1))
        self.assertEqual(
            result["比对结果"].tolist(),
            [analysis.MATCH_STATUS_INCOMPLETE, analysis.MATCH_STATUS_UNMATCHED],
        )
        self.assertEqual(result.loc[0, "比对时间差"], "24小时")
        self.assertEqual(result.loc[0, "比对金额差"], 2.0)
        self.assertEqual(result.loc[1, "比对时间差"], "")
        self.assertEqual(result.loc[1, "比对金额差"], "")

    def test_duplicate_medical_rows_in_same_event_share_prescription(self) -> None:
        config = analysis.DEFAULT_COLUMN_CONFIG
        medical = pd.DataFrame(
            [
                {
                    config.medical_person_name: "张三",
                    config.medical_settlement_time: "2026-07-14 10:00:00",
                    config.medical_product_name: "阿莫西林",
                },
                {
                    config.medical_person_name: "张三",
                    config.medical_settlement_time: "2026-07-14 10:00:00",
                    config.medical_product_name: "阿莫西林",
                },
            ]
        )
        prescription = pd.DataFrame(
            [
                {
                    config.prescription_outpatient_id: "M001",
                    config.prescription_person_name: "张三",
                    config.prescription_submit_time: "2026-07-14 10:00:00",
                    config.prescription_product_name: "阿莫西林",
                }
            ]
        )

        with redirect_stdout(StringIO()):
            result, normal, after_medicine, missing = analysis.compare_prescriptions_to_medical(
                medical,
                prescription,
                config,
            )

        self.assertEqual((normal, after_medicine, missing), (2, 0, 0))
        self.assertEqual(result["处方端门诊号"].tolist(), ["M001", "M001"])
        self.assertEqual(
            result["处方情况"].tolist(),
            [analysis.PRESCRIPTION_STATUS_NORMAL, analysis.PRESCRIPTION_STATUS_NORMAL],
        )

    def test_prescription_is_not_reused_across_settlement_events(self) -> None:
        config = analysis.DEFAULT_COLUMN_CONFIG
        medical = pd.DataFrame(
            [
                {
                    config.medical_person_name: "张三",
                    config.medical_settlement_time: "2026-07-14 10:00:00",
                    config.medical_product_name: "阿莫西林",
                },
                {
                    config.medical_person_name: "张三",
                    config.medical_settlement_time: "2026-07-14 10:30:00",
                    config.medical_product_name: "阿莫西林",
                },
            ]
        )
        prescription = pd.DataFrame(
            [
                {
                    config.prescription_outpatient_id: "M001",
                    config.prescription_person_name: "张三",
                    config.prescription_submit_time: "2026-07-14 10:00:00",
                    config.prescription_product_name: "阿莫西林",
                }
            ]
        )

        with redirect_stdout(StringIO()):
            result, normal, after_medicine, missing = analysis.compare_prescriptions_to_medical(
                medical,
                prescription,
                config,
            )

        self.assertEqual((normal, after_medicine, missing), (1, 0, 1))
        self.assertEqual(
            result["处方情况"].tolist(),
            [analysis.PRESCRIPTION_STATUS_NORMAL, analysis.PRESCRIPTION_STATUS_MISSING],
        )


if __name__ == "__main__":
    unittest.main()
