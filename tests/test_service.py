from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest

from supplydesk import cli
from supplydesk.service import OrderService


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_student_discount_at_exactly_5000_cents(self):
        quote = self.service.quote("student", [{"product_id": "bag", "quantity": 2}])
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["total_cents"], 4500)

    def test_regular_delivery_over_threshold_is_free(self):
        quote = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], "delivery")
        self.assertEqual(quote["subtotal_cents"], 12000)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 12000)
        
    def test_zero_quantity_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 0}])
            
            
    def test_cancel_restores_stock(self):
        before = self.service.catalog()
        order = self.service.place_order("regular", [{"product_id": "hoodie", "quantity": 2}])
        self.service.cancel_order(order["order_id"])
        self.assertEqual(self.service.catalog(), before)
        
    def test_cancelling_twice_does_not_restore_stock_twice(self):
        order = self.service.place_order("regular", [{"product_id": "hoodie", "quantity": 2}])
        self.service.cancel_order(order["order_id"])
        self.service.cancel_order(order["order_id"])
        stock = self.service.catalog()[2]["stock"]
        self.assertEqual(stock, 5) 
        
    def test_same_product_on_two_lines_cannot_exceed_stock(self):
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [
                {"product_id": "bag", "quantity": 3},
                {"product_id": "bag", "quantity": 3},
            ])

    def test_student_no_discount_just_below_5000_cents(self):
        quote = self.service.quote("student", [
            {"product_id": "notebook", "quantity": 5},
            {"product_id": "pen-pack", "quantity": 3},
        ])
        self.assertEqual(quote["subtotal_cents"], 4750)
        self.assertEqual(quote["discount_cents"], 0)

    def test_delivery_free_at_exactly_10000_cents(self):
        quote = self.service.quote("regular", [{"product_id": "bag", "quantity": 4}], "delivery")
        self.assertEqual(quote["subtotal_cents"], 10000)
        self.assertEqual(quote["delivery_cents"], 0)

    def test_delivery_charged_just_below_10000_cents(self):
        quote = self.service.quote("regular", [
            {"product_id": "bag", "quantity": 2},
            {"product_id": "hoodie", "quantity": 1},
            {"product_id": "pen-pack", "quantity": 1},
        ], "delivery")
        self.assertEqual(quote["subtotal_cents"], 9750)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 10350)

    def test_quantity_100_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 100}])

    def test_unknown_product_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "laptop", "quantity": 1}])

    def test_quote_matches_placed_order(self):
        items = [{"product_id": "hoodie", "quantity": 2}, {"product_id": "mug", "quantity": 1}]
        quote = self.service.quote("student", items, "delivery")
        order = self.service.place_order("student", items, "delivery")
        for key in quote:
            self.assertEqual(order[key], quote[key])

    def test_place_order_student_delivery_pricing(self):
        order = self.service.place_order("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assertEqual(order["subtotal_cents"], 8000)
        self.assertEqual(order["discount_cents"], 800)
        self.assertEqual(order["delivery_cents"], 600)
        self.assertEqual(order["total_cents"], 7800)

    def test_get_order_unknown_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.get_order("ORD-9999")

    def test_cancel_order_unknown_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.cancel_order("ORD-9999")



class ExpressDeliveryTests(unittest.TestCase):
    """CR-01: express delivery."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_regular_two_notebooks_express(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}], "express")
        self.assertEqual(quote["fulfillment"], "express")
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)

    def test_student_two_hoodies_express(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "express")
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)

    def test_express_fee_never_waived(self):
        items = [{"product_id": "hoodie", "quantity": 3}]
        standard = self.service.quote("regular", items, "delivery")
        express = self.service.quote("regular", items, "express")
        self.assertEqual(standard["total_cents"], 12000)
        self.assertEqual(express["delivery_cents"], 1200)
        self.assertEqual(express["total_cents"], 13200)

    def test_express_quote_matches_placed_order(self):
        items = [{"product_id": "hoodie", "quantity": 2}]
        quote = self.service.quote("student", items, "express")
        order = self.service.place_order("student", items, "express")
        for key in quote:
            self.assertEqual(order[key], quote[key])

    def test_express_order_kept_after_reopen_and_cancel(self):
        order = self.service.place_order("student", [{"product_id": "hoodie", "quantity": 2}], "express")
        reopened = OrderService(self.path)
        cancelled = reopened.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["fulfillment"], "express")
        self.assertEqual(cancelled["delivery_cents"], 1200)
        self.assertEqual(cancelled["total_cents"], 8400)
        self.assertEqual(reopened.catalog()[2]["stock"], 5)

    def test_other_fulfillment_still_rejected(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 1}], "courier")

    def test_cli_express_quote(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = cli.main(["--data", str(self.path), "quote", "--customer", "student",
                               "--fulfillment", "express", "--item", "hoodie:2"])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["total_cents"], 8400)


if __name__ == "__main__":
    unittest.main()