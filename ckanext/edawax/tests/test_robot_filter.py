"""
Test for the helper function that will filter robots based on UserAgent
from the counter
"""

import ckanext.edawax.helpers as helpers


class TestRobotFilter(object):
    def test_filter_bot_pass(self):
        user_agent = "bot"
        result = helpers.is_robot(user_agent)
        assert result == True, "{} is a robot".format(user_agent)

    def test_filter_google_pass(self):
        user_agent = "google"
        result = helpers.is_robot(user_agent)
        assert result == True, "{} is a robot".format(user_agent)

    def test_filter_python_pass(self):
        user_agent = "python"
        result = helpers.is_robot(user_agent)
        assert result == True, "{} is a robot".format(user_agent)

    def test_filter_mozilla_fail(self):
        user_agent = "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"
        result = helpers.is_robot(user_agent)
        assert result == False, "{} is not a robot".format(user_agent)

    def test_filter_chrome_fail(self):
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
        result = helpers.is_robot(user_agent)
        assert result == False, "{} is not a robot".format(user_agent)
