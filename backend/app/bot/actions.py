import os

from .dom_walker import DomWalker
from .auth_mixin import AuthMixin
from .profile_mixin import ProfileMixin
from .publish_mixin import PublishMixin
from .interact_mixin import InteractMixin


class FBActions(AuthMixin, ProfileMixin, PublishMixin, InteractMixin):
    """Facebook actions (login, publish) using Playwright Page + Camoufox.

    Requires an active Playwright Page created by BrowserManager.

    Methods are organized into mixins:
    - AuthMixin: login, account picker, login modal
    - ProfileMixin: profile switching (page/personal)
    - PublishMixin: publishing to groups/fanpages, composer, background
    - InteractMixin: like, comment, message
    """

    def __init__(self, page, account_email: str):
        self.page = page
        self.account_email = account_email
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        self.dom = DomWalker(page)
        self._personal_profile_name: str | None = None
        self._current_page_name: str | None = None
        self._last_password: str | None = None
