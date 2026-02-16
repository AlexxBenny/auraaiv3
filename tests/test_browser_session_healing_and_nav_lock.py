import time
import threading

from core.browser_session_manager import BrowserSession, BrowserSessionManager
from tools.browsers._engine.playwright import PlaywrightEngine


class FakePage:
    def __init__(self, closed=False, url="about:blank"):
        self._closed = closed
        self.url = url

    def is_closed(self):
        return self._closed

    def goto(self, url, timeout=None):
        # simulate successful navigation by setting url
        self.url = url


class FakePageRaise:
    def __init__(self, url):
        self.url = url

    def is_closed(self):
        return False

    def goto(self, url, timeout=None):
        raise Exception("interrupted")


class FakeContext:
    def __init__(self, pages=None):
        self.pages = pages or []

    def new_page(self):
        p = FakePage()
        self.pages.append(p)
        return p


def test_ensure_page_reattaches():
    session = BrowserSession(session_id="s1", browser_type="chromium")
    # cached page not in context
    session.page = FakePage(url="about:blank")
    ctx_page = FakePage(url="https://example.com")
    session.context = FakeContext(pages=[ctx_page])
    assert session.ensure_page() is True
    assert session.page is ctx_page


def test_ensure_page_creates_new_page():
    session = BrowserSession(session_id="s2", browser_type="chromium")
    session.page = None
    session.context = FakeContext(pages=[])
    assert session.ensure_page() is True
    assert session.page is not None
    assert session.page in session.context.pages


def test_nav_lock_serialization():
    session = BrowserSession(session_id="s3", browser_type="chromium")
    seq = []

    def worker(label):
        with session.nav_lock:
            seq.append(label)
            time.sleep(0.01)
            seq.append(label + "_done")

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # ensure operations are serialized (grouped per-thread)
    assert seq in (["a", "a_done", "b", "b_done"], ["b", "b_done", "a", "a_done"])


def test_engine_navigate_interrupted_but_final_matches():
    engine = PlaywrightEngine()
    page = FakePageRaise(url="https://target.com/search?q=term")
    res = engine.navigate(page, "https://target.com/search?q=term")
    assert res is True


