"""
Test for the helper function that will filter robots based on UserAgent
from the counter
"""

import ckanext.edawax.helpers as helpers

class TestTrackPath(object):
    def test_journal_landing_page_true(self):
        path = '/journals/something-here'
        result = helpers.track_path(path)
        assert result == True, "Page should be tracked"

    def test_dataset_landing_page_true(self):
        path = '/dataset/a-data-resource'
        result = helpers.track_path(path)
        assert result == True, "Page should be tracked"

    def test_resource_landing_page_false(self):
        path = '/dataset/ksja-fp9w4-ru8jf-i4398r/resource/123a-123123-675234-34908g'
        result = helpers.track_path(path)
        assert result == False, "Page shouldn't be tracked"

    def test_resource_download_true(self):
        path = '/dataset/194349da-742a-415e-9525-6f8d66e7c7d5/resource/7155a289-940f-419f-85d3-d27128369551/download/image.png'
        result = helpers.track_path(path)
        assert result == True, "Page should be tracked"

class TestRobotFilter(object):
    def test_filter_bot_true(self):
        user_agent = "bot"
        result = helpers.is_robot(user_agent)
        assert result == True, "{} is a robot".format(user_agent)


    def test_filter_google_true(self):
        user_agent = "google"
        result = helpers.is_robot(user_agent)
        assert result == True, "{} is a robot".format(user_agent)


    def test_filter_python_true(self):
        user_agent = "python"
        result = helpers.is_robot(user_agent)
        assert result == True, "{} is a robot".format(user_agent)


    def test_filter_mozilla_false(self):
        user_agent = "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"
        result = helpers.is_robot(user_agent)
        assert result == False, "{} is not a robot".format(user_agent)


    def test_filter_chrome_false(self):
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
        result = helpers.is_robot(user_agent)
        assert result == False, "{} is not a robot".format(user_agent)


    def test_filter_common_bots_full_true(self):
        """
        most commont according to keycdn.com/blog/web-crawlers
        """
        bots = ["Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
                "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
                "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
                "Sogou web spider/4.0(+http://www.sogou.com/docs/help/webmasters.htm#07)"]

        for bot in bots:
            result = helpers.is_robot(bot)
            assert result == True, "{} is a robot".format(bot)


    def test_filter_bot_no_match_false(self):
        user_agent = "fake_user_agent"
        result = helpers.is_robot(user_agent)
        assert result == False, "{} is not a thing".format(user_agent)
