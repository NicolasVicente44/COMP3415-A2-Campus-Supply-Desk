from pathlib import Path
import tempfile
import unittest

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
    

if __name__ == "__main__":
    unittest.main()