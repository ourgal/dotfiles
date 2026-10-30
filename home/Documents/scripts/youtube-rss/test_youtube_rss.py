import unittest
from unittest.mock import patch, MagicMock
from youtube_rss import (
    youtube_url_to_rss,
    channel_feed,
    user_feed,
    ConversionError,
    _normalize_url,
    _extract_channel_id,
)

class TestYoutubeRSS(unittest.TestCase):
    def test_channel_feed(self):
        cid = "UCBR8-60-B28hp2BmDPdntcQ"
        expected = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        self.assertEqual(channel_feed(cid), expected)
        with self.assertRaises(ConversionError):
            channel_feed("invalid_id")

    def test_user_feed(self):
        user = "YouTube"
        expected = f"https://www.youtube.com/feeds/videos.xml?user={user}"
        self.assertEqual(user_feed(user), expected)
        with self.assertRaises(ConversionError):
            user_feed("invalid user name!")

    def test_normalize_url(self):
        self.assertEqual(_normalize_url("@handle"), "https://www.youtube.com/@handle")
        self.assertEqual(_normalize_url("/c/test"), "https://www.youtube.com/c/test")
        self.assertEqual(_normalize_url("youtube.com/@handle"), "https://youtube.com/@handle")
        with self.assertRaises(ConversionError):
            _normalize_url("")
        with self.assertRaises(ConversionError):
            _normalize_url("not_a_url")

    def test_youtube_url_to_rss_direct(self):
        cid = "UCBR8-60-B28hp2BmDPdntcQ"
        expected = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        
        # Direct channel ID
        self.assertEqual(youtube_url_to_rss(cid), expected)
        # Channel URL
        self.assertEqual(
            youtube_url_to_rss(f"https://www.youtube.com/channel/{cid}"),
            expected,
        )
        # User URL
        user_expected = "https://www.youtube.com/feeds/videos.xml?user=Google"
        self.assertEqual(
            youtube_url_to_rss("https://www.youtube.com/user/Google"),
            user_expected,
        )

    def test_youtube_url_to_rss_feed_passthrough(self):
        cid = "UCBR8-60-B28hp2BmDPdntcQ"
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        self.assertEqual(youtube_url_to_rss(feed_url), feed_url)

    @patch("youtube_rss._fetch_page")
    def test_youtube_url_to_rss_handle_resolution(self, mock_fetch):
        cid = "UCBR8-60-B28hp2BmDPdntcQ"
        html_content = f'<html><link rel="canonical" href="https://www.youtube.com/channel/{cid}"></html>'
        mock_fetch.return_value = (html_content, "https://www.youtube.com/@test")

        expected = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        self.assertEqual(youtube_url_to_rss("https://www.youtube.com/@test"), expected)

    def test_extract_channel_id(self):
        cid = "UCBR8-60-B28hp2BmDPdntcQ"
        
        # Test feed link in HTML
        html1 = f'<html><link rel="alternate" type="application/rss+xml" href="https://www.youtube.com/feeds/videos.xml?channel_id={cid}"></html>'
        self.assertEqual(_extract_channel_id(html1, "http://example.com"), cid)
        
        # Test canonical link
        html2 = f'<html><link rel="canonical" href="https://www.youtube.com/channel/{cid}"></html>'
        self.assertEqual(_extract_channel_id(html2, "http://example.com"), cid)

        # Test embedded JSON ID
        html3 = f'<html>{{"externalId":"{cid}"}}</html>'
        self.assertEqual(_extract_channel_id(html3, "http://example.com"), cid)

if __name__ == "__main__":
    unittest.main()
