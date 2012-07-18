u"""Cheshire3 Extractor Unittests.

Extractor configurations may be customized by the user. For the purposes of 
unittesting, configuration files will be ignored and Extractor instances will
be instantiated using configuration data defined within this testing module, 
and tests carried out on instances.
"""

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from lxml import etree
from xml.sax.saxutils import escape
from datetime import datetime
from copy import deepcopy

from cheshire3.extractor import Extractor, SimpleExtractor

from cheshire3.test.testConfigParser import Cheshire3ObjectTestCase


class SimpleExtractorTestCase(Cheshire3ObjectTestCase):

    @classmethod
    def _get_class(cls):
        return SimpleExtractor

    def _get_config(self):
        return etree.XML('''
        <subConfig type="extractor" id="{0.__name__}">
            <objectType>{0.__module__}.{0.__name__}</objectType>
        </subConfig>
        '''.format(self._get_class()))

    def setUp(self):
        Cheshire3ObjectTestCase.setUp(self)

    def _get_process_string_tests(self):
        # Return a list of tuples containing test pairs:
        # (string to be tokenized, expected tokens list)
        return [('spam',
                 {'spam': {
                      'text': 'spam',
                      'occurences': 1,
                      'proxLoc': [-1]
                      }
                  }),
                (u'spam',
                 {u'spam': {
                      'text': u'spam',
                      'occurences': 1,
                      'proxLoc': [-1]
                      }
                 })]

    def _get_process_node_tests(self):
        return [(etree.XML('<data>spam</data>'),
                 {'spam': {
                      'text': 'spam',
                      'occurences': 1,
                      'proxLoc': [-1]
                      }
                  })]
        
    def _get_process_xpathResult_tests(self):
        tests = [([[inp]], expected)
                for inp, expected
                in self._get_process_node_tests()]
        tests.extend([
                      ([[etree.XML('<data>spam</data>'),
                         etree.XML('<data>egg</data>')]],
                       {'spam': {
                           'text': 'spam',
                           'occurences': 1,
                           'proxLoc': [-1]
                           },
                        'egg': {
                            'text': 'egg',
                            'occurences': 1,
                            'proxLoc': [-1]
                            }
                        }),
                      ([[etree.XML('<data>spam</data>')],
                        [etree.XML('<data2>spam</data2>')]],
                       {'spam': {
                           'text': 'spam',
                           'occurences': 2,
                           'proxLoc': [-1, -1]
                           }
                        })
        ])
        return tests

    def test_process_string(self):
        for inp, expected in self._get_process_string_tests():
            output = self.testObj.process_string(self.session, inp)
            self.assertDictEqual(output, expected)

    def test_process_node(self):
        for inp, expected in self._get_process_node_tests():
            output = self.testObj.process_node(self.session, inp)
            self.assertDictEqual(output, expected)

    def test_process_xpathResult(self):
        for inp, expected in self._get_process_xpathResult_tests():
            output = self.testObj.process_xpathResult(self.session, inp)
            self.assertDictEqual(output, expected)

    def test_mergeHash(self):
        "Check that mergeHash correctly merges hashes."
        a = {'spam': {
                 'occurences': 1,
                 'positions': [1, 2, 3]
             },
             'egg': {
                 'occurences': 2,
                 'positions': [1, 2, 3]
             },
             'bacon': {
                 'occurences': 3,
                 'positions': [1, 1, 1]
             }
        }
        b = {'spam': {
                 'occurences': 1,
                 'positions': [4, 5, 6]
             },
             'sausage': {
                 'occurences': 1,
                 'positions': [1, 2, 3]
             },
        }
        # send in copy of a so that original not modified - messes up testing
        c = self.testObj._mergeHash(deepcopy(a), b)
        # Check that all key in a and b are in c
        for k in a:
            self.assertIn(k, c)
        for k in b:
            self.assertIn(k, c)
        # Check that values are correct sums/extensions
        for ck, chash in c.iteritems():
            av = a.get(ck, {'occurences': 0, 'positions': []})
            bv = b.get(ck, {'occurences': 0, 'positions': []})
            for sharedk, mergedval in chash.iteritems():
                self.assertEqual(mergedval, av[sharedk] + bv[sharedk])


def load_tests(loader, tests, pattern):
    # Alias loader.loadTestsFromTestCase for sake of line lengths
    ltc = loader.loadTestsFromTestCase 
    suite = ltc(SimpleExtractorTestCase)
    return suite


if __name__ == '__main__':
    tr = unittest.TextTestRunner(verbosity=2)
    tr.run(load_tests(unittest.defaultTestLoader, [], 'test*.py'))
