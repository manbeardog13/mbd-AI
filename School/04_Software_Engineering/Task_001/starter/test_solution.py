import unittest
from solution import parse_port

class Tests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_port(' 443 '), 443)
    def test_bounds(self):
        for value in ('0', '-1', '65536'):
            with self.assertRaises(ValueError): parse_port(value)
    def test_bad_types(self):
        for value in (True, 'abc', None):
            with self.assertRaises(ValueError): parse_port(value)

if __name__ == '__main__': unittest.main()
