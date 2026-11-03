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


if __name__ == "__main__":
    unittest.main()