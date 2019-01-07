from __future__ import absolute_import
from __future__ import print_function
from os import path
from time import time
from pprint import pprint
import pytest
from collections import Counter
from lxml.etree import ParserError

from .utilities import BASE_TEST_URL
from .openwpmtest import OpenWPMTest
from ..automation.TaskManager import TaskManager
from ..automation.CommandSequence import CommandSequence
from ..automation.Commands.utils.banner_utils import fetch_banner_list
from ..automation.Commands.utils.banner_utils import find_banners_by_selectors, parse_banner_list
from ..automation.utilities import db_utils


class TestBannerDetection(OpenWPMTest):
    """Test `detect_cookie_banner` command and underlying utility functions"""

    B_LIST_LOC = path.join(path.dirname(path.abspath(__file__)),
                           'test_pages/banners/bannerlist_201812.txt')  # or bannerlist_201812
    B_TEST_HTML_LOC = path.join(path.dirname(path.abspath(__file__)), 'test_pages/banners/')

    def test_list_fetch(self, tmpdir):
        data_dir = str(tmpdir)
        fetch_banner_list(data_dir)
        assert path.isfile(path.join(data_dir, 'bannerlist.txt'))

    def test_parse_banner_list(self, tmpdir):
        # needs input, either a short-static list, or a saved list, which we use here
        banner_list = parse_banner_list(self.B_LIST_LOC)
        assert type(banner_list) is dict
        assert '__global__' in banner_list
        assert '__unknown__' in banner_list
        assert 10000 > len(banner_list) > 1000
        assert 10000 > len(banner_list['__global__']) > 1000
        assert 10 < len(banner_list['__unknown__']) < 500
        assert banner_list['motorola.de'] == ['#Privacy_banner', '#Privacy_container', '#Privacy_bg'] or \
               banner_list['motorola.de'] == ['#Privacy_banner']  # latter is for bannerlist_201812

    def test_banner_simple_none(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'simple.html')).read()
        n, banners = find_banners_by_selectors('', page_html, self.B_LIST_LOC)
        assert n >= 6179 and len(banners) == 0  # 9120 for bannerlist_201812

    def test_banner_empty_raise(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'empty.html')).read()
        with pytest.raises(ParserError):
            find_banners_by_selectors('', page_html, self.B_LIST_LOC)

    @pytest.mark.slow
    def test_banner_empty_via_browser(self, tmpdir):
        manager_params, browser_params = self.get_test_config(str(tmpdir))
        browser_params[0]['banner_list_location'] = self.B_LIST_LOC
        manager = TaskManager(manager_params, browser_params)
        cs = CommandSequence(BASE_TEST_URL + '/banners/empty.html')
        cs.get()
        cs.detect_cookie_banner()  # should/will not raise
        manager.execute_command_sequence(cs)
        manager.close()
        rows = db_utils.query_db(manager_params['db'], "SELECT * FROM cookie_banners")
        assert not rows

    def test_banner_tudelft(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'tudelft.html')).read()
        n, banners = find_banners_by_selectors('http://tudelft.nl', page_html, self.B_LIST_LOC)
        assert n >= 6179 and len(banners) == 2
        assert banners[0].selector.startswith('#cookieNotice')
        assert banners[0].tag == 'div' and banners[0].id == 'cookieNotice'
        assert banners[0].text.startswith('Deze website')
        assert banners[1].selector.startswith('.CookiesOK')
        assert banners[1].tag == 'a' and banners[1].id == ''
        assert banners[1].text == 'Ik ga akkoord'

    @pytest.mark.slow
    def test_banner_tudelft_via_browser(self, tmpdir):
        manager_params, browser_params = self.get_test_config(str(tmpdir))
        browser_params[0]['banner_list_location'] = self.B_LIST_LOC
        manager = TaskManager(manager_params, browser_params)
        cs = CommandSequence(BASE_TEST_URL + '/banners/tudelft.html')
        cs.get()
        cs.detect_cookie_banner()
        manager.execute_command_sequence(cs)
        manager.close()
        db = manager_params['db']
        rows = db_utils.query_db(db, "SELECT id, visit_id, crawl_id, url, "
                                     "css_selector, selected_tag, selected_id, "
                                     "pos_x, pos_y, size_h, size_w, `text` "
                                     "FROM cookie_banners")
        assert len(rows) == 2
        # note that size & location slightly differ if the CSS & images aren't loaded
        assert rows[0][7] == 8 and rows[0][8] > 480 and rows[0][9] == 127 and rows[0][10] > 1200
        assert rows[0][5] == 'div' and rows[0][11].startswith('Deze website')
        assert rows[1][7] > 980 and rows[1][8] > 560 and rows[1][9] == 35 and rows[1][10] == 130
        assert rows[1][5] == 'a' and rows[1][11] == 'Ik ga akkoord'

    def test_banner_derstandard(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'derstandard.html')).read()
        n, banners = find_banners_by_selectors('http://derstandard.at', page_html, self.B_LIST_LOC)
        if banners:
            # on bannerlist_201812 the page layout has changed so this old saved page doesn't match.
            assert n >= 6180 and len(banners) == 1  # 9120 for bannerlist_201812
            assert banners[0].selector == '#privacypolicy' and banners[0].tag == 'div'
            assert banners[0].text.endswith('Mehr Informationen OK')

    def test_banner_googlenl(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'google-nl.html')).read()
        n, banners = find_banners_by_selectors('http://www.google.nl', page_html, self.B_LIST_LOC)
        assert n >= 6186 and 1 <= len(banners) <= 2  # 9137 & 2 for bannerlist_201812
        assert banners[0].selector == '#cnsh' and banners[0].tag == 'div'
        assert banners[0].text.startswith('A privacy reminder from Google')

    def test_banner_youtube(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'youtube.html')).read()
        n, banners = find_banners_by_selectors('http://youtube.com', page_html, self.B_LIST_LOC)
        assert n >= 6179 and len(banners) == 1  # 9120 for bannerlist_201812
        assert banners[0].selector.endswith('ytd-consent-bump-renderer')
        assert banners[0].text.find('A privacy reminder from YouTube') != -1

    @pytest.mark.slow
    def test_banner_youtube_via_browser(self, tmpdir):
        manager_params, browser_params = self.get_test_config(str(tmpdir))
        browser_params[0]['banner_list_location'] = self.B_LIST_LOC
        manager = TaskManager(manager_params, browser_params)
        cs = CommandSequence(BASE_TEST_URL + '/banners/youtube.html')
        cs.get()
        cs.detect_cookie_banner(timeout=120)  # banner detect can take quite long on YouTube
        manager.execute_command_sequence(cs)
        manager.close()
        db = manager_params['db']
        rows = db_utils.query_db(db, "SELECT id, visit_id, crawl_id, url, "
                                     "css_selector, selected_tag, selected_id, "
                                     "pos_x, pos_y, size_h, size_w, `text` "
                                     "FROM cookie_banners")
        assert len(rows) == 1
        assert rows[0][7] == 0 and rows[0][8] == 0 and rows[0][9] == 56 and rows[0][10] > 1200
        assert rows[0][5] == 'ytd-consent-bump-renderer'
        assert 'A privacy reminder from YouTube' in rows[0][11]

    def test_banner_nunl(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'nu-nl.html')).read()
        n, banners = find_banners_by_selectors('http://nu.nl', page_html, self.B_LIST_LOC)
        count_by_sel = Counter([b.selector for b in banners])
        # one of the selectors matches 368 elements on thepage.
        assert n >= 6179 and len(banners) > 10  # 9120 for bannerlist_201812
        assert len(count_by_sel) == 2 and min(count_by_sel.values()) == 1

    def test_banner_faznet(self, tmpdir):
        page_html = open(path.join(self.B_TEST_HTML_LOC, 'faznet.html')).read()
        n, banners = find_banners_by_selectors('http://faz.net', page_html, self.B_LIST_LOC)
        # this seems to be some strange anti-ad-blocker mechanism?
        assert len(banners) == 1
        assert banners[0].tag == 'div' and banners[0].id == 'cookieContainer'
        assert banners[0].text.strip() == ''
