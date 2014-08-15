from ci.lib.test_case import MultinodeTestCase


class ML2MutinodeTest(MultinodeTestCase):

    @classmethod
    def setUpClass(cls):
        MultinodeTestCase.setUpClass()

    def test_tempest(self):
        pass