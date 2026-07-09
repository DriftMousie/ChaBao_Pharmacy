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


if __name__ == "__main__":
    unittest.main()

